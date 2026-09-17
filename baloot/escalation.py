"""Double (دبل), Three (ثري), Four (فور) and Qahwa (قهوة).

The calls
---------
All calls happen after the deal is complete and before the first card is led.

* **Hokom.** Either defender may call Double, open or closed. The buyer may
  answer Three. The doubler may answer Four, open or closed. The buyer may
  answer Qahwa. Only the buyer and the doubler take part after the first
  Double (federation rules, art. 7-5).
* **Sun and Ashkal.** A defender may call Double only when the defending team
  has 100 points or fewer and the buying team has more than 100 (art. 7-2).
  There is no Three, Four, Qahwa or closed play in Sun (art. 7-1).
* **Closed (مقفل).** Nobody may lead a trump unless their hand is all trumps.
  The last call decides: Three and Qahwa are always open (art. 7-5).

Scoring of each level is in ``scoring.py``.

How the AI decides
------------------
``EscalationAdvisor`` estimates the value of each legal call by Monte Carlo
simulation, reusing the same machinery as card play:

1. A knowledge base holds what is known: the agent's own hand and the ground
   card, which is in the hand of the player who took it.
2. The CSP sampler draws complete deals consistent with that knowledge.
   Deals are *rejection-sampled* against a simple model of the other calls:
   the buyer's hand must be strong enough for the contract it bought (the same
   hand-strength measure the bidding heuristic uses), and a doubler's hand must
   show some trump strength. This is opponent modelling: without it the
   samples would ignore what the bids reveal.
3. Each sampled deal is played out with the greedy policy (open and, if
   needed, closed) and scored at every level the call could lead to.
4. The call with the best average score difference (our points minus theirs)
   is chosen, but a raise must beat passing by ``margin`` game points, because
   the estimate is noisy and ignores the opponents' chance to re-raise.

A Qahwa is valued as the points still needed to win the match (if won) or the
points the opponents still need (if lost).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .bidding import ASHKAL_MAX_GAIN, HOKOM_THRESHOLD, SUN_THRESHOLD, hokom_strength, sun_strength
from .cards import Card
from .knowledge import KnowledgeBase
from .policies import greedy_card
from .rules import (HOKOM, LAST_TRICK_BONUS, detect_projects, resolve_declarations, team_of,
                    trick_points, trick_winner)
from .sampler import DealSampler
from .scoring import DOUBLE, FOUR, NORMAL, QAHWA, THREE, score_hand

PASS = "Pass"
CALL_DOUBLE = "Double"
CALL_DOUBLE_CLOSED = "Double closed"
CALL_THREE = "Three"
CALL_FOUR = "Four"
CALL_FOUR_CLOSED = "Four closed"
CALL_QAHWA = "Qahwa"

# call -> (level, closed?)
CALL_EFFECT = {
    CALL_DOUBLE: (DOUBLE, False),
    CALL_DOUBLE_CLOSED: (DOUBLE, True),
    CALL_THREE: (THREE, False),
    CALL_FOUR: (FOUR, False),
    CALL_FOUR_CLOSED: (FOUR, True),
    CALL_QAHWA: (QAHWA, False),
}

CALL_LABELS = {
    PASS: "No raise  بدون",
    CALL_DOUBLE: "Double  دبل",
    CALL_DOUBLE_CLOSED: "Double, closed  دبل مقفل",
    CALL_THREE: "Three  ثري",
    CALL_FOUR: "Four  فور",
    CALL_FOUR_CLOSED: "Four, closed  فور مقفل",
    CALL_QAHWA: "Qahwa  قهوة",
}

SUN_DOUBLE_LIMIT = 100
DOUBLER_MODEL_STRENGTH = 4.0   # assumed minimum trump strength of a player who doubled a Hokom


def sun_double_allowed(totals: Sequence[int], declarer_team: int) -> bool:
    """Art. 7-2: defenders at 100 or fewer, buyers above 100."""
    return totals[1 - declarer_team] <= SUN_DOUBLE_LIMIT < totals[declarer_team]


@dataclass(frozen=True)
class EscalationView:
    """Everything a seat may see when it is asked to raise."""
    pid: int
    hand: Tuple[Card, ...]
    mode: str
    trump: Optional[str]
    buyer: int
    taker: int              # the player who took the ground card
    ground_card: Card
    dealer: int
    level: int
    locked: bool
    doubler: Optional[int]
    options: Tuple[str, ...]
    totals: Tuple[int, int]
    target: int = 152


def play_out(hands: Dict[int, List[Card]], leader: int, mode: str, trump: Optional[str],
             locked: bool) -> List[int]:
    """Play a full deal with the greedy policy. Returns team card points."""
    hands = {p: list(h) for p, h in hands.items()}
    points = [0, 0]
    for trick in range(8):
        table: List[Tuple[int, Card]] = []
        for i in range(4):
            pid = (leader + i) % 4
            card = greedy_card(pid, hands[pid], table, mode, trump, locked)
            hands[pid].remove(card)
            table.append((pid, card))
        leader = trick_winner(table, mode, trump)
        points[team_of(leader)] += trick_points(table, mode, trump) + (LAST_TRICK_BONUS if trick == 7 else 0)
    return points


class EscalationAdvisor:
    def __init__(self, samples: int = 24, margin: float = 4.0,
                 rng: Optional[random.Random] = None, attempts_per_sample: int = 12):
        self.samples = samples
        self.margin = margin
        self.rng = rng or random.Random()
        self.attempts_per_sample = attempts_per_sample

    # -- model of the other players' calls ------------------------------------

    def _plausible(self, deal: Dict[int, List[Card]], view: EscalationView) -> bool:
        if view.buyer != view.pid:
            buyer_hand = deal[view.buyer]
            if view.mode == HOKOM:
                if hokom_strength(buyer_hand, view.trump) < HOKOM_THRESHOLD:
                    return False
            else:
                # Sun needs SUN_THRESHOLD with the ground card; Ashkal leaves the
                # ground card with the partner, so the caller needs a little less.
                needed = SUN_THRESHOLD if view.taker == view.buyer else SUN_THRESHOLD - ASHKAL_MAX_GAIN
                if sun_strength(buyer_hand) < needed:
                    return False
        if (view.mode == HOKOM and view.doubler is not None and view.doubler != view.pid
                and hokom_strength(deal[view.doubler], view.trump) < DOUBLER_MODEL_STRENGTH):
            return False
        return True

    def _deals(self, view: EscalationView) -> List[Dict[int, List[Card]]]:
        kb = KnowledgeBase(view.pid)
        if view.taker != view.pid:
            kb.known[view.taker].add(view.ground_card)
        sampler = DealSampler(kb, view.hand, self.rng)
        deals, fallback = [], []
        for _ in range(self.samples * self.attempts_per_sample):
            if len(deals) >= self.samples:
                break
            deal = sampler.sample()
            if deal is None:
                break
            (deals if self._plausible(deal, view) else fallback).append(deal)
        # If the model is too strict for this hand, top up with unfiltered deals.
        return deals + fallback[:self.samples - len(deals)]

    # -- evaluation -----------------------------------------------------------

    def evaluate(self, view: EscalationView) -> Dict[str, float]:
        """Average (our points - their points) for each legal call."""
        effects = {PASS: (view.level, view.locked)}
        effects.update({o: CALL_EFFECT[o] for o in view.options if o in CALL_EFFECT})
        locks = {lock for _, lock in effects.values()}
        me = team_of(view.pid)
        declarer_team = team_of(view.buyer)
        leader = (view.dealer + 1) % 4
        totals = {o: 0.0 for o in effects}

        deals = self._deals(view)
        for deal in deals:
            decl = resolve_declarations(
                {p: detect_projects(deal[p], view.mode, view.trump) for p in range(4)}, view.mode)
            card_points = {lock: play_out(deal, leader, view.mode, view.trump, lock) for lock in locks}
            for option, (level, lock) in effects.items():
                hs = score_hand(view.mode, declarer_team, card_points[lock],
                                decl.project_points, decl.baloot_points, level)
                if hs.qahwa:
                    value = (view.target - view.totals[me] if hs.winner == me
                             else -(view.target - view.totals[1 - me]))
                else:
                    value = hs.final[me] - hs.final[1 - me]
                totals[option] += value
        n = max(1, len(deals))
        return {o: v / n for o, v in totals.items()}

    def decide(self, view: EscalationView) -> str:
        if len(view.options) <= 1:
            return PASS
        values = self.evaluate(view)
        best = max(values, key=values.get)
        if best != PASS and values[best] - values[PASS] >= self.margin:
            return best
        return PASS


def heuristic_escalation(view: EscalationView) -> str:
    """Cheap rule of thumb used by the baseline players."""
    if view.mode != HOKOM:
        if CALL_DOUBLE in view.options and sun_strength(view.hand) >= 9.0:
            return CALL_DOUBLE
        return PASS
    strength = hokom_strength(view.hand, view.trump)
    trumps = sum(1 for c in view.hand if c.suit == view.trump)
    if CALL_DOUBLE_CLOSED in view.options and strength >= 9.0 and trumps >= 3:
        return CALL_DOUBLE_CLOSED
    if CALL_THREE in view.options and strength >= 12.0:
        return CALL_THREE
    return PASS

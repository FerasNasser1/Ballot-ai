"""Agents that play Baloot.

``BalootAgent`` combines the pieces:

* Knowledge base (``knowledge.py``) tracks what can be proven about hidden hands.
* CSP sampler (``sampler.py``) draws full deals consistent with that knowledge.
* Alpha-beta (``search.py``) solves each sampled deal.
* Perfect Information Monte Carlo (PIMC) averages the move values over many
  samples, as in GIB for bridge (Ginsberg, JAIR 2001).
* Mushtra bidding (``bidding.py``) uses the ML model when present, otherwise a
  hand-strength heuristic.
* Double / Three / Four / Qahwa (``escalation.py``) are decided by Monte Carlo
  rollouts over sampled deals.

Threading: ``plan_move`` runs on the GUI thread and copies everything the search
needs into a ``DecisionTask``. ``DecisionTask.run`` can then run on a worker
thread without touching live game state.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .bidding import MushtraEngine
from .cards import Card
from .escalation import EscalationAdvisor, EscalationView, heuristic_escalation
from .knowledge import KnowledgeBase
from .policies import cheapness as _cheapness
from .policies import greedy_card
from .rules import legal_moves
from .sampler import DealSampler
from .search import TrickSearch

HORIZON = 2          # tricks searched early in the hand
HORIZON_FULL = 4     # search to the end once this many cards remain


@dataclass(frozen=True)
class PlayerView:
    """Everything a seat is allowed to see when it must play."""
    pid: int
    hand: Tuple[Card, ...]
    table: Tuple[Tuple[int, Card], ...]
    mode: str
    trump: Optional[str]
    locked: bool = False      # closed (مقفل) Hokom: no trump leads


@dataclass
class DecisionTask:
    view: PlayerView
    kb: KnowledgeBase
    seed: int
    samples: int
    time_budget: float

    def run(self) -> Card:
        v = self.view
        legal = legal_moves(v.hand, v.table, v.mode, v.trump, v.locked)
        if len(legal) == 1:
            return legal[0]

        rng = random.Random(self.seed)
        sampler = DealSampler(self.kb, v.hand, rng)
        cards_left = len(v.hand)
        # Search to the end of the hand once few cards remain; otherwise
        # the current trick plus one more.
        horizon = cards_left if cards_left <= HORIZON_FULL else HORIZON
        search = TrickSearch(v.pid, v.mode, v.trump, horizon, v.locked)

        totals: Dict[Card, float] = {c: 0.0 for c in legal}
        done = 0
        deadline = time.monotonic() + self.time_budget
        while done < self.samples and (done < 3 or time.monotonic() < deadline):
            deal = sampler.sample()
            if deal is None:
                break
            for card, value in search.move_values(deal, v.table, legal).items():
                totals[card] += value
            done += 1

        if done == 0:
            return min(legal, key=lambda c: _cheapness(c, v.mode, v.trump))
        # Ties go to the cheaper card, so the agent doesn't waste high cards.
        return max(legal, key=lambda c: (round(totals[c] / done, 6),
                                         tuple(-x for x in _cheapness(c, v.mode, v.trump))))


class BalootAgent:
    def __init__(self, pid: int, samples: int = 30, time_budget: float = 1.0,
                 bidder: Optional[MushtraEngine] = None, seed: Optional[int] = None,
                 escalation_samples: int = 24):
        self.pid = pid
        self.samples = samples
        self.time_budget = time_budget
        self.kb = KnowledgeBase(pid)
        self.bidder = bidder or MushtraEngine()
        self.rng = random.Random(seed)
        self.advisor = EscalationAdvisor(samples=escalation_samples,
                                         rng=random.Random(self.rng.randrange(2**31)))

    # Observer interface used by the engine
    def new_round(self) -> None:
        self.kb.reset()

    def observe_contract(self, mode, trump, locked, taker, ground_card) -> None:
        self.kb.observe_contract(mode, trump, locked, taker, ground_card)

    def observe_play(self, pid, card, table_before, mode, trump) -> None:
        self.kb.observe_play(pid, card, table_before, mode, trump)

    def observe_declaration(self, pid, cards) -> None:
        self.kb.observe_declaration(pid, cards)

    # Decisions
    def choose_bid(self, hand: Sequence[Card], public_card: Card, bid_round: int, options=None):
        return self.bidder.decide(hand, public_card, bid_round, options)

    def choose_escalation(self, view: EscalationView) -> str:
        return self.advisor.decide(view)

    def plan_move(self, view: PlayerView) -> DecisionTask:
        return DecisionTask(view, self.kb.snapshot(), self.rng.randrange(2**31),
                            self.samples, self.time_budget)

    def choose_card(self, view: PlayerView) -> Card:
        return self.plan_move(view).run()


# ---------------------------------------------------------------------------
# Baselines for evaluation (simulate.py)
# ---------------------------------------------------------------------------

class _BaselineBase:
    def __init__(self, pid: int, seed: Optional[int] = None):
        self.pid = pid
        self.rng = random.Random(seed)
        self.bidder = MushtraEngine()

    def new_round(self): pass
    def observe_contract(self, *args): pass
    def observe_play(self, *args): pass
    def observe_declaration(self, *args): pass

    def choose_bid(self, hand, public_card, bid_round, options=None):
        return self.bidder.decide(hand, public_card, bid_round, options)

    def choose_escalation(self, view: EscalationView) -> str:
        return heuristic_escalation(view)


class RandomPlayer(_BaselineBase):
    """Random legal cards. With ``random_calls=True`` it also raises at random,
    which the tests use to reach closed, tripled and Qahwa hands."""

    def __init__(self, pid: int, seed: Optional[int] = None, random_calls: bool = False):
        super().__init__(pid, seed)
        self.random_calls = random_calls

    def choose_card(self, view: PlayerView) -> Card:
        return self.rng.choice(legal_moves(view.hand, view.table, view.mode, view.trump, view.locked))

    def choose_escalation(self, view: EscalationView) -> str:
        if self.random_calls:
            return self.rng.choice(view.options)
        return super().choose_escalation(view)


class GreedyPlayer(_BaselineBase):
    """Win the trick as cheaply as possible; otherwise throw the cheapest card.
    Never tries to beat a partner who is already winning."""

    def choose_card(self, view: PlayerView) -> Card:
        return greedy_card(self.pid, view.hand, view.table, view.mode, view.trump, view.locked)

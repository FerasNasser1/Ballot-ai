"""Game engine: one match of Baloot, with no GUI code.

The GUI and ``simulate.py`` both drive this class, so the rules and scoring
live in exactly one place and can be tested headless.

Seats: 0 = human (or any player), 1 = right, 2 = partner, 3 = left.
Play passes to the right, so seat ``p + 1`` is on the right of seat ``p``.

A hand goes through these phases::

    BIDDING  ->  DOUBLING  ->  PLAYING <-> TRICK_COMPLETE  ->  ROUND_OVER / MATCH_OVER

Bidding (Mushtra)
-----------------
Bidding order: dealer's right, dealer's partner, dealer's left, dealer.

Round 1: Pass, Hokom (trump = ground card's suit), Sun, or Ashkal.
  * After a Hokom bid, every other player gets one chance, in bidding order,
    to overcall with Sun (or Ashkal), even if they passed before. The earliest
    seat has priority. If nobody overcalls, the Hokom stands.
  * Sun or Ashkal ends the bidding.
  * If all four pass, round 2 starts.
Round 2: Pass (ولا), Hokom in another suit (حكم ثاني), Sun, or Ashkal.
  * After a Hokom thani bid, players who have not spoken yet in round 2 may
    overcall with Sun or Ashkal. A player who passed may not come back.
  * If all four pass, the cards are redealt.

Ashkal (أشكل): only the dealer and the player on the dealer's left may call it.
The contract is Sun, the caller is the buyer, and the caller's partner takes
the ground card. With ``ashkal_requires_hokom=True`` Ashkal is only allowed
after the opposing team has bid Hokom (federation rules, art. 8-1).

Doubling happens after the rest of the cards are dealt: see ``escalation.py``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from .agent import PlayerView
from .bidding import BUY_ASHKAL, BUY_HOKOM, BUY_HOKOM_THANI, BUY_SUN, PASS
from .cards import SUITS, Card, shuffled_deck
from .escalation import (CALL_DOUBLE, CALL_DOUBLE_CLOSED, CALL_EFFECT, CALL_FOUR, CALL_FOUR_CLOSED,
                         CALL_QAHWA, CALL_THREE, EscalationView, sun_double_allowed)
from .rules import (HOKOM, LAST_TRICK_BONUS, SUN, DeclarationResult, Project, detect_projects,
                    legal_moves, partner_of, resolve_declarations, team_of, trick_points,
                    trick_winner)
from .scoring import DOUBLE, FOUR, NORMAL, QAHWA, THREE, score_hand

TARGET_SCORE = 152


class Phase(Enum):
    BIDDING = auto()
    DOUBLING = auto()
    PLAYING = auto()
    TRICK_COMPLETE = auto()
    ROUND_OVER = auto()
    MATCH_OVER = auto()


class Observer(Protocol):
    def new_round(self) -> None: ...
    def observe_contract(self, mode, trump, locked, taker, ground_card) -> None: ...
    def observe_play(self, pid: int, card: Card, table_before, mode, trump) -> None: ...
    def observe_declaration(self, pid: int, cards: Sequence[Card]) -> None: ...


class IllegalAction(Exception):
    pass


@dataclass
class TrickResult:
    winner: int
    points: int
    trick_number: int                      # 1..8
    declarations: Optional[DeclarationResult] = None   # set after trick 1
    round_result: Optional["RoundResult"] = None       # set after trick 8


@dataclass
class RoundResult:
    mode: str
    trump: Optional[str]
    buyer: int
    card_points: List[int]
    base: List[int]               # converted card points (sum 16 or 26)
    project_points: List[int]     # projects + Baloot, before any multiplying
    final: List[int]              # added to the match score
    buyer_failed: bool            # the buyer's team lost the hand
    totals_after: List[int] = field(default_factory=lambda: [0, 0])
    level: int = NORMAL
    locked: bool = False
    doubler: Optional[int] = None
    ashkal: bool = False
    winner: Optional[int] = None  # team that won the hand
    qahwa: bool = False
    baloot_points: List[int] = field(default_factory=lambda: [0, 0])   # part of project_points


class GameEngine:
    def __init__(self, observers: Optional[Sequence[Observer]] = None,
                 rng: Optional[random.Random] = None, ashkal_requires_hokom: bool = False):
        self.rng = rng or random.Random()
        self.observers: List[Observer] = list(observers or [])
        self.ashkal_requires_hokom = ashkal_requires_hokom
        self.totals = [0, 0]
        self.history: List[RoundResult] = []
        self.dealer = self.rng.randrange(4)
        self.phase = Phase.ROUND_OVER
        self.hands: Dict[int, List[Card]] = {p: [] for p in range(4)}
        self.table: List[Tuple[int, Card]] = []
        self.mode: Optional[str] = None
        self.trump: Optional[str] = None
        self.buyer: Optional[int] = None
        self.taker: Optional[int] = None
        self.ashkal = False
        self.level = NORMAL
        self.locked = False
        self.doubler: Optional[int] = None
        self._qahwa_winner: Optional[int] = None
        self._bid_queue: List[int] = []
        self._escalation_queue: List[int] = []

    def _notify(self, method: str, *args) -> None:
        for obs in self.observers:
            handler = getattr(obs, method, None)
            if handler is not None:
                handler(*args)

    # ------------------------------------------------------------------ round

    def start_round(self) -> None:
        if self.phase == Phase.MATCH_OVER:
            raise IllegalAction("Match is over")
        self.dealer = (self.dealer + 1) % 4
        deck = shuffled_deck(self.rng)
        self.hands = {p: deck[p * 5:(p + 1) * 5] for p in range(4)}
        self.public_card: Card = deck[20]
        self._stock = deck[21:]

        self.bid_starter = (self.dealer + 1) % 4
        self.bid_order = [(self.dealer + i) % 4 for i in (1, 2, 3, 4)]
        self.bid_round = 1
        self._bid_queue = list(self.bid_order)
        self.hokom_bid: Optional[Tuple[int, str]] = None
        self.bid_log: List[Tuple[int, int, str, Optional[str]]] = []   # (round, pid, action, suit)

        self.mode, self.trump, self.buyer, self.taker = None, None, None, None
        self.ashkal = False
        self.level, self.locked, self.doubler = NORMAL, False, None
        self._escalation_queue = []
        self.escalation_log: List[Tuple[int, str]] = []
        self.table = []
        self.turn = self.bid_starter
        self.tricks_played = 0
        self.card_points = [0, 0]
        self.projects: Dict[int, List[Project]] = {}
        self.declarations: Optional[DeclarationResult] = None
        self.phase = Phase.BIDDING
        self._notify("new_round")

    # ---------------------------------------------------------------- bidding

    @property
    def current_bidder(self) -> Optional[int]:
        return self._bid_queue[0] if self.phase == Phase.BIDDING and self._bid_queue else None

    def ashkal_eligible(self, pid: int) -> bool:
        """Only the dealer and the player on the dealer's left may call Ashkal."""
        if pid not in (self.dealer, (self.dealer + 3) % 4):
            return False
        if self.ashkal_requires_hokom:
            return self.hokom_bid is not None and team_of(self.hokom_bid[0]) != team_of(pid)
        return True

    def bid_options(self) -> List[str]:
        pid = self.current_bidder
        if pid is None:
            return []
        options = [PASS, BUY_SUN]
        if self.hokom_bid is None:
            options.append(BUY_HOKOM if self.bid_round == 1 else BUY_HOKOM_THANI)
        if self.ashkal_eligible(pid):
            options.append(BUY_ASHKAL)
        return options

    def thani_suits(self) -> List[str]:
        return [s for s in SUITS if s != self.public_card.suit]

    def apply_bid(self, pid: int, action: str, trump: Optional[str] = None) -> str:
        """Returns one of:
        "pass", "hokom" (a Hokom bid now waits for overcalls), "second_round",
        "redeal", or "bought" (bidding is over and the deal is complete)."""
        if self.phase != Phase.BIDDING or pid != self.current_bidder:
            raise IllegalAction(f"Player {pid} cannot bid now")
        if action not in self.bid_options():
            raise IllegalAction(f"{action!r} is not available to player {pid} now")

        if action == BUY_HOKOM_THANI and trump not in self.thani_suits():
            raise IllegalAction("Hokom thani needs a suit other than the ground card's")
        if action == BUY_HOKOM:
            trump = self.public_card.suit
        if action in (PASS, BUY_SUN, BUY_ASHKAL):
            trump = None
        self.bid_log.append((self.bid_round, pid, action, trump))

        if action in (BUY_SUN, BUY_ASHKAL):
            self._finish_bidding(pid, SUN, None, ashkal=action == BUY_ASHKAL)
            return "bought"

        self._bid_queue.pop(0)
        if action in (BUY_HOKOM, BUY_HOKOM_THANI):
            self.hokom_bid = (pid, trump)
            if self.bid_round == 1:
                # Everyone else may overcall with Sun, earliest seat first.
                self._bid_queue = [p for p in self.bid_order if p != pid]
            if not self._bid_queue:
                self._finish_bidding(pid, HOKOM, trump)
                return "bought"
            return "hokom"

        # PASS
        if self._bid_queue:
            return "pass"
        if self.hokom_bid is not None:
            self._finish_bidding(self.hokom_bid[0], HOKOM, self.hokom_bid[1])
            return "bought"
        if self.bid_round == 1:
            self.bid_round = 2
            self._bid_queue = list(self.bid_order)
            return "second_round"
        self.phase = Phase.ROUND_OVER
        return "redeal"

    def _finish_bidding(self, buyer: int, mode: str, trump: Optional[str], ashkal: bool = False) -> None:
        self.mode, self.trump, self.buyer, self.ashkal = mode, trump, buyer, ashkal
        self.taker = partner_of(buyer) if ashkal else buyer
        self._bid_queue = []
        self._complete_deal()

    def _complete_deal(self) -> None:
        self.hands[self.taker].append(self.public_card)
        stock = list(self._stock)
        for offset in range(4):
            p = (self.bid_starter + offset) % 4
            need = 8 - len(self.hands[p])
            self.hands[p].extend(stock[:need])
            stock = stock[need:]
        assert not stock and all(len(h) == 8 for h in self.hands.values())

        self.projects = {p: detect_projects(self.hands[p], self.mode, self.trump) for p in range(4)}
        self.declarations = resolve_declarations(self.projects, self.mode)
        self.turn = self.bid_starter

        defenders = [p for p in self.bid_order if team_of(p) != team_of(self.buyer)]
        if self.mode == HOKOM or sun_double_allowed(self.totals, team_of(self.buyer)):
            self._escalation_queue = defenders
            self.phase = Phase.DOUBLING
        else:
            self._begin_play()

    # --------------------------------------------------------------- doubling

    @property
    def escalation_turn(self) -> Optional[int]:
        if self.phase != Phase.DOUBLING or not self._escalation_queue:
            return None
        return self._escalation_queue[0]

    def escalation_options(self) -> List[str]:
        pid = self.escalation_turn
        if pid is None:
            return []
        if self.level == NORMAL:
            return [PASS, CALL_DOUBLE, CALL_DOUBLE_CLOSED] if self.mode == HOKOM else [PASS, CALL_DOUBLE]
        if self.level == DOUBLE:
            return [PASS, CALL_THREE]
        if self.level == THREE:
            return [PASS, CALL_FOUR, CALL_FOUR_CLOSED]
        if self.level == FOUR:
            return [PASS, CALL_QAHWA]
        return []

    def escalation_view(self, pid: int) -> EscalationView:
        return EscalationView(pid, tuple(self.hands[pid]), self.mode, self.trump, self.buyer,
                              self.taker, self.public_card, self.dealer, self.level, self.locked,
                              self.doubler, tuple(self.escalation_options()), tuple(self.totals),
                              TARGET_SCORE)

    def apply_escalation(self, pid: int, action: str) -> str:
        """Returns "pass" (next defender may still double), "raised", or "done"
        (play can start)."""
        if pid != self.escalation_turn:
            raise IllegalAction(f"Player {pid} cannot raise now")
        if action not in self.escalation_options():
            raise IllegalAction(f"{action!r} is not available now")
        self.escalation_log.append((pid, action))
        self._escalation_queue.pop(0)

        if action == PASS:
            if self.level == NORMAL and self._escalation_queue:
                return "pass"
            self._escalation_queue = []
            self._begin_play()
            return "done"

        self.level, self.locked = CALL_EFFECT[action]
        if self.level == DOUBLE:
            self.doubler = pid
        if self.mode == SUN or self.level == QAHWA:
            self._escalation_queue = []
            self._begin_play()
            return "done"
        # Only the buyer and the doubler raise after the first Double.
        self._escalation_queue = [self.buyer if self.level in (DOUBLE, FOUR) else self.doubler]
        return "raised"

    def _begin_play(self) -> None:
        self.phase = Phase.PLAYING
        self.turn = self.bid_starter
        self._notify("observe_contract", self.mode, self.trump, self.locked, self.taker, self.public_card)

    # ------------------------------------------------------------------- play

    def view_for(self, pid: int) -> PlayerView:
        return PlayerView(pid, tuple(self.hands[pid]), tuple(self.table), self.mode, self.trump,
                          self.locked)

    def legal_moves(self, pid: int) -> List[Card]:
        if self.phase != Phase.PLAYING or pid != self.turn:
            return []
        return legal_moves(self.hands[pid], self.table, self.mode, self.trump, self.locked)

    def current_winner(self) -> Optional[int]:
        return trick_winner(self.table, self.mode, self.trump) if self.table else None

    def play(self, pid: int, card: Card) -> None:
        if card not in self.legal_moves(pid):
            raise IllegalAction(f"Player {pid} cannot play {card} now")
        table_before = list(self.table)
        self.hands[pid].remove(card)
        self.table.append((pid, card))
        self._notify("observe_play", pid, card, table_before, self.mode, self.trump)
        if len(self.table) == 4:
            self.phase = Phase.TRICK_COMPLETE
        else:
            self.turn = (self.turn + 1) % 4

    def resolve_trick(self) -> TrickResult:
        if self.phase != Phase.TRICK_COMPLETE:
            raise IllegalAction("Trick is not complete")
        winner = trick_winner(self.table, self.mode, self.trump)
        points = trick_points(self.table, self.mode, self.trump)
        self.tricks_played += 1
        if self.tricks_played == 8:
            points += LAST_TRICK_BONUS
        self.card_points[team_of(winner)] += points
        self.table = []
        self.turn = winner
        result = TrickResult(winner, points, self.tricks_played)

        if self.tricks_played == 1:
            # Declarations are shown after the first trick.
            for pid, projs in self.declarations.shown.items():
                for p in projs:
                    self._notify("observe_declaration", pid, p.cards)
            result.declarations = self.declarations

        if self.tricks_played == 8:
            result.round_result = self._score_round()
        else:
            self.phase = Phase.PLAYING
        return result

    # ---------------------------------------------------------------- scoring

    def _score_round(self) -> RoundResult:
        decl = self.declarations
        hs = score_hand(self.mode, team_of(self.buyer), self.card_points,
                        decl.project_points, decl.baloot_points, self.level)
        final = list(hs.final)
        if hs.qahwa:
            # Qahwa wins the match outright; the sheet shows the winner reaching the target.
            w = hs.winner
            final = [0, 0]
            final[w] = max(TARGET_SCORE, self.totals[1 - w] + 1) - self.totals[w]
            self._qahwa_winner = w

        for t in (0, 1):
            self.totals[t] += final[t]
        result = RoundResult(self.mode, self.trump, self.buyer, list(self.card_points),
                             list(hs.game_points), list(decl.team_points), final,
                             not hs.declarer_won, list(self.totals), self.level, self.locked,
                             self.doubler, self.ashkal, hs.winner, hs.qahwa, list(decl.baloot_points))
        self.history.append(result)

        if hs.qahwa or (max(self.totals) >= TARGET_SCORE and self.totals[0] != self.totals[1]):
            self.phase = Phase.MATCH_OVER
        else:
            self.phase = Phase.ROUND_OVER
        return result

    @property
    def match_winner(self) -> Optional[int]:
        if self.phase != Phase.MATCH_OVER:
            return None
        if self._qahwa_winner is not None:
            return self._qahwa_winner
        return 0 if self.totals[0] > self.totals[1] else 1

    def new_match(self) -> None:
        self.totals = [0, 0]
        self.history = []
        self._qahwa_winner = None
        self.phase = Phase.ROUND_OVER

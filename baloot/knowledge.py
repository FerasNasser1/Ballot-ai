"""Knowledge base: what one agent can prove about the hidden hands.

Facts are only ever derived from public information (cards played, the table
at the time of each play, and revealed declarations) plus the play rules in
``rules.legal_moves``, which every seat, including the human, must obey. That
makes every inference *sound*: the real deal always satisfies the knowledge
base, which ``tests/test_knowledge.py`` checks over many random games.

Inference rules (applied each time a card is observed):

R1  A player who does not follow the lead suit is void in that suit.
R2  Hokom, non-trump lead, player is void, partner is NOT winning, and the
    player discards a non-trump  ->  the player is void in trump.
R3  Hokom, player plays a trump that does not beat the highest trump already
    on the table, in a situation where over-trumping was compulsory
    ->  the player holds no trump higher than that table trump.
R4  A card from a revealed declaration is in that player's hand until played.
R5  A played card is in nobody's hand (and leaves the "known" set).
R6  The ground card is in the hand of the player who took it (the buyer, or
    the buyer's partner after Ashkal) until it is played.
R7  Closed (مقفل) Hokom, player LEADS a trump  ->  the player holds only trumps,
    i.e. is void in the three other suits (leading a trump is illegal otherwise).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple

from .cards import SUITS, Card
from .rules import (HOKOM, TRUMP_ORDER, highest_trump_on_table, partner_of,
                    trick_winner, trump_strength)


class KnowledgeBase:
    HAND_SIZE = 8

    def __init__(self, my_id: int):
        self.my_id = my_id
        self.reset()

    def reset(self) -> None:
        self.played: Set[Card] = set()
        self.played_by: List[int] = [0, 0, 0, 0]
        self.voids: Dict[int, Set[str]] = {p: set() for p in range(4)}
        self.known: Dict[int, Set[Card]] = {p: set() for p in range(4)}
        self.excluded: Dict[int, Set[Card]] = {p: set() for p in range(4)}
        self.log: List[str] = []
        self.locked = False

    # -- perception ---------------------------------------------------------

    def observe_contract(self, mode: Optional[str], trump: Optional[str], locked: bool,
                         taker: int, ground_card: Card) -> None:
        self.locked = bool(locked and mode == HOKOM)
        # R6
        if taker != self.my_id and ground_card not in self.played and ground_card not in self.known[taker]:
            self.known[taker].add(ground_card)
            self.log.append(f"R6: P{taker} holds {ground_card!r} (ground card)")

    def observe_play(self, pid: int, card: Card, table_before: Sequence[Tuple[int, Card]],
                     mode: Optional[str], trump: Optional[str]) -> None:
        if table_before:
            self._infer_from_play(pid, card, table_before, mode, trump)
        elif self.locked and mode == HOKOM and card.suit == trump:
            # R7
            for suit in SUITS:
                if suit != trump:
                    self._add_void(pid, suit, "R7")

        # R5
        self.played.add(card)
        self.played_by[pid] += 1
        for p in range(4):
            self.known[p].discard(card)

    def observe_declaration(self, pid: int, cards: Sequence[Card]) -> None:
        # R4
        newly = [c for c in cards if c not in self.played and c not in self.known[pid]]
        self.known[pid].update(newly)
        if newly:
            self.log.append(f"R4: P{pid} holds {' '.join(map(repr, newly))} (declared)")

    # -- inference ----------------------------------------------------------

    def _infer_from_play(self, pid, card, table_before, mode, trump) -> None:
        lead = table_before[0][1].suit

        if card.suit != lead:
            self._add_void(pid, lead, "R1")
            if mode != HOKOM or lead == trump:
                return
            partner_winning = trick_winner(table_before, mode, trump) == partner_of(pid)
            if partner_winning:
                return  # any card was legal, nothing more to learn
            if card.suit != trump:
                self._add_void(pid, trump, "R2")
            else:
                self._exclude_higher_trumps(pid, card, table_before, trump)
            return

        if mode == HOKOM and lead == trump:
            self._exclude_higher_trumps(pid, card, table_before, trump)

    def _exclude_higher_trumps(self, pid, card, table_before, trump) -> None:
        top = highest_trump_on_table(table_before, trump)
        if top is None or trump_strength(card) > trump_strength(top):
            return
        newly = []
        for rank in TRUMP_ORDER[trump_strength(top) + 1:]:
            c = Card(trump, rank)
            if c not in self.played and c not in self.excluded[pid]:
                self.excluded[pid].add(c)
                newly.append(c)
        if newly:
            self.log.append(f"R3: P{pid} holds none of {newly}")

    def _add_void(self, pid: int, suit: str, rule: str) -> None:
        if suit not in self.voids[pid]:
            self.voids[pid].add(suit)
            self.log.append(f"{rule}: P{pid} is void in {suit}")

    # -- queries ------------------------------------------------------------

    def cards_in_hand(self, pid: int) -> int:
        return self.HAND_SIZE - self.played_by[pid]

    def can_hold(self, pid: int, card: Card) -> bool:
        return (card not in self.played and card.suit not in self.voids[pid]
                and card not in self.excluded[pid])

    def snapshot(self) -> "KnowledgeBase":
        """Independent copy for the search thread."""
        kb = KnowledgeBase(self.my_id)
        kb.played = set(self.played)
        kb.played_by = list(self.played_by)
        kb.voids = {p: set(s) for p, s in self.voids.items()}
        kb.known = {p: set(s) for p, s in self.known.items()}
        kb.excluded = {p: set(s) for p, s in self.excluded.items()}
        kb.locked = self.locked
        return kb

    def consistent_with(self, hands: Dict[int, Sequence[Card]]) -> bool:
        """True if a full deal satisfies every fact. Used by the tests."""
        for pid, hand in hands.items():
            if len(hand) != self.cards_in_hand(pid):
                return False
            if not self.known[pid] <= set(hand):
                return False
            if any(not self.can_hold(pid, c) for c in hand):
                return False
        return True

    def describe(self) -> str:
        lines = []
        for p in range(4):
            if p == self.my_id:
                continue
            voids = ", ".join(s for s in SUITS if s in self.voids[p]) or "none"
            known = " ".join(map(repr, sorted(self.known[p], key=repr))) or "none"
            lines.append(f"P{p}: void in {voids}; known cards {known}; "
                         f"{len(self.excluded[p])} trumps excluded")
        return "\n".join(lines)

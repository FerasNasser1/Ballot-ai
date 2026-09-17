"""Baloot rules as pure functions.

Every function here takes the game situation as arguments instead of reading a
shared mutable object. That makes the rules safe to call from the search thread
and easy to unit-test.

A *table* is a list of ``(player_id, Card)`` tuples in play order. The lead suit
is always the suit of the first card, so it can never get out of sync with the
table (the original code stored it separately).

Seats 0..3 play in order 0 -> 1 -> 2 -> 3. Teams are {0, 2} and {1, 3}.

Scoring of a finished hand (including Double, Three, Four and Qahwa) lives in
``scoring.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .cards import RANKS, SUITS, Card

HOKOM = "Hokom"
SUN = "Sun"

TRUMP_ORDER = ("7", "8", "Q", "K", "10", "A", "9", "J")
PLAIN_ORDER = ("7", "8", "9", "J", "Q", "K", "10", "A")

PLAIN_POINTS = {"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0, "8": 0, "7": 0}
TRUMP_POINTS = {"J": 20, "9": 14, "A": 11, "10": 10, "K": 4, "Q": 3, "8": 0, "7": 0}
LAST_TRICK_BONUS = 10

Table = List[Tuple[int, Card]]


def team_of(player_id: int) -> int:
    return player_id % 2


def partner_of(player_id: int) -> int:
    return (player_id + 2) % 4


def is_trump(card: Card, mode: Optional[str], trump: Optional[str]) -> bool:
    return mode == HOKOM and card.suit == trump


def trump_strength(card: Card) -> int:
    return TRUMP_ORDER.index(card.rank)


def plain_strength(card: Card) -> int:
    return PLAIN_ORDER.index(card.rank)


def card_points(card: Card, mode: Optional[str], trump: Optional[str]) -> int:
    if is_trump(card, mode, trump):
        return TRUMP_POINTS[card.rank]
    return PLAIN_POINTS[card.rank]


def trick_points(table: Sequence[Tuple[int, Card]], mode: Optional[str], trump: Optional[str]) -> int:
    return sum(card_points(c, mode, trump) for _, c in table)


def total_card_points(mode: str) -> int:
    """162 in Hokom, 130 in Sun (including the last-trick bonus)."""
    return (152 if mode == HOKOM else 120) + LAST_TRICK_BONUS


def beats(challenger: Card, current: Card, mode: Optional[str], trump: Optional[str]) -> bool:
    """Does ``challenger`` beat the card currently winning the trick?

    ``current`` is always either the lead suit or a trump, so a plain card can
    only win by being the same suit and higher.
    """
    if mode == HOKOM:
        c_trump = challenger.suit == trump
        w_trump = current.suit == trump
        if c_trump and not w_trump:
            return True
        if w_trump and not c_trump:
            return False
        if c_trump and w_trump:
            return trump_strength(challenger) > trump_strength(current)
    return challenger.suit == current.suit and plain_strength(challenger) > plain_strength(current)


def trick_winner(table: Sequence[Tuple[int, Card]], mode: Optional[str], trump: Optional[str]) -> int:
    if not table:
        raise ValueError("Empty table has no winner")
    win_pid, win_card = table[0]
    for pid, card in table[1:]:
        if beats(card, win_card, mode, trump):
            win_pid, win_card = pid, card
    return win_pid


def highest_trump_on_table(table: Sequence[Tuple[int, Card]], trump: Optional[str]) -> Optional[Card]:
    trumps = [c for _, c in table if c.suit == trump]
    return max(trumps, key=trump_strength) if trumps else None


# ---------------------------------------------------------------------------
# Constraint satisfaction: which cards may legally be played
# ---------------------------------------------------------------------------

def legal_moves(hand: Sequence[Card], table: Sequence[Tuple[int, Card]],
                mode: Optional[str], trump: Optional[str], locked: bool = False) -> List[Card]:
    """Filter a hand down to the cards that satisfy the play constraints.

    1. Leading: any card, except in a *closed* (مقفل) Hokom game, where a trump
       may only be led by a player whose hand is all trumps.
    2. Must follow the lead suit if possible.
       In Hokom, when trump is led, must beat the highest trump if possible.
    3. Void in the lead suit, Hokom, partner not currently winning:
       must play a trump if you have one, and must over-trump if possible.
    4. Otherwise any card.
    """
    if not table:
        if locked and mode == HOKOM:
            non_trumps = [c for c in hand if c.suit != trump]
            if non_trumps:
                return non_trumps
        return list(hand)

    lead = table[0][1].suit
    follow = [c for c in hand if c.suit == lead]

    if follow:
        if mode == HOKOM and lead == trump:
            top = highest_trump_on_table(table, trump)
            higher = [c for c in follow if trump_strength(c) > trump_strength(top)]
            if higher:
                return higher
        return follow

    if mode == HOKOM:
        me = (table[0][0] + len(table)) % 4
        if trick_winner(table, mode, trump) == partner_of(me):
            return list(hand)
        trumps = [c for c in hand if c.suit == trump]
        if trumps:
            top = highest_trump_on_table(table, trump)
            if top is not None:
                higher = [c for c in trumps if trump_strength(c) > trump_strength(top)]
                if higher:
                    return higher
            return trumps

    return list(hand)


# ---------------------------------------------------------------------------
# Projects (Mashari)
# ---------------------------------------------------------------------------

# Raw values; converted to round points by dividing by 10 (Hokom) or 5 (Sun).
RAW_SIRA = 20
RAW_FIFTY = 50
RAW_HUNDRED = 100
RAW_FOUR_HUNDRED = 400
RAW_BALOOT = 20


@dataclass(frozen=True)
class Project:
    name: str            # "Sira", "50", "100", "400", "Baloot"
    cards: Tuple[Card, ...]
    raw: int             # raw value used for comparison
    top_rank: int        # tie-breaker: index of the highest rank in RANKS

    def points(self, mode: str) -> int:
        return self.raw // 10 if mode == HOKOM else self.raw // 5

    @property
    def is_baloot(self) -> bool:
        return self.name == "Baloot"


def _runs(suit_cards: List[Card]) -> List[List[Card]]:
    ordered = sorted(suit_cards, key=lambda c: RANKS.index(c.rank))
    runs, current = [], []
    for card in ordered:
        if current and RANKS.index(card.rank) == RANKS.index(current[-1].rank) + 1:
            current.append(card)
        else:
            if len(current) >= 3:
                runs.append(current)
            current = [card]
    if len(current) >= 3:
        runs.append(current)
    return runs


def detect_projects(hand: Sequence[Card], mode: str, trump: Optional[str] = None) -> List[Project]:
    """Find the projects in an 8-card hand.

    Simplifications (documented in the README): a card may count toward both
    a sequence and a four-of-a-kind, and a run longer than five is worth 100.
    """
    projects: List[Project] = []

    for suit in SUITS:
        for run in _runs([c for c in hand if c.suit == suit]):
            top = RANKS.index(run[-1].rank)
            if len(run) == 3:
                projects.append(Project("Sira", tuple(run), RAW_SIRA, top))
            elif len(run) == 4:
                projects.append(Project("50", tuple(run), RAW_FIFTY, top))
            else:
                projects.append(Project("100", tuple(run), RAW_HUNDRED, top))

    for rank in ("10", "J", "Q", "K", "A"):
        same = [c for c in hand if c.rank == rank]
        if len(same) == 4:
            if rank == "A" and mode == SUN:
                projects.append(Project("400", tuple(same), RAW_FOUR_HUNDRED, RANKS.index(rank)))
            else:
                projects.append(Project("100", tuple(same), RAW_HUNDRED, RANKS.index(rank)))

    if mode == HOKOM and trump:
        kq = [c for c in hand if c.suit == trump and c.rank in ("K", "Q")]
        if len(kq) == 2:
            projects.append(Project("Baloot", tuple(kq), RAW_BALOOT, RANKS.index("K")))

    return projects


@dataclass
class DeclarationResult:
    winning_team: Optional[int]                      # None when tied or nobody declared
    team_points: List[int] = field(default_factory=lambda: [0, 0])      # projects + Baloot
    shown: Dict[int, List[Project]] = field(default_factory=dict)  # player -> projects revealed
    project_points: List[int] = field(default_factory=lambda: [0, 0])   # projects only
    baloot_points: List[int] = field(default_factory=lambda: [0, 0])    # Baloot only


def resolve_declarations(projects: Dict[int, List[Project]], mode: str) -> DeclarationResult:
    """Only the team holding the best project scores (and shows) its projects.

    Best = highest raw value, then highest top rank. An exact tie scores nothing
    for either team, which was the original code's tie rule. Baloot is outside
    the comparison and always scores for its holder. Projects and Baloot are
    also reported separately because a doubled hand multiplies projects but
    never Baloot (federation rules, art. 5-4).
    """
    best: List[Tuple[int, int]] = [(-1, -1), (-1, -1)]
    for pid, projs in projects.items():
        for p in projs:
            if not p.is_baloot:
                best[team_of(pid)] = max(best[team_of(pid)], (p.raw, p.top_rank))

    if best[0] > best[1]:
        winner: Optional[int] = 0
    elif best[1] > best[0]:
        winner = 1
    else:
        winner = None

    result = DeclarationResult(winning_team=winner)
    for pid, projs in projects.items():
        t = team_of(pid)
        for p in projs:
            if p.is_baloot:
                result.team_points[t] += p.points(mode)
                result.baloot_points[t] += p.points(mode)
            elif winner == t:
                result.team_points[t] += p.points(mode)
                result.project_points[t] += p.points(mode)
                result.shown.setdefault(pid, []).append(p)
    return result

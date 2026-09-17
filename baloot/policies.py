"""Simple card-play policies shared by the baselines and the Monte Carlo
rollouts used for doubling decisions.

Kept separate from ``agent.py`` so that ``escalation.py`` can use them without
a circular import.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from .cards import Card
from .rules import beats, card_points, is_trump, legal_moves, plain_strength, trick_winner, trump_strength


def cheapness(card: Card, mode: Optional[str], trump: Optional[str]):
    """Lower is cheaper to throw away."""
    strength = trump_strength(card) if is_trump(card, mode, trump) else plain_strength(card)
    return (is_trump(card, mode, trump), card_points(card, mode, trump), strength)


def greedy_card(pid: int, hand: Sequence[Card], table: Sequence[Tuple[int, Card]],
                mode: str, trump: Optional[str], locked: bool = False) -> Card:
    """Win the trick as cheaply as possible; otherwise throw the cheapest card.
    Never tries to beat a partner who is already winning. Leads its strongest
    non-trump."""
    legal = legal_moves(hand, table, mode, trump, locked)
    cheap = lambda c: cheapness(c, mode, trump)
    if not table:
        return max(legal, key=lambda c: (plain_strength(c) if not is_trump(c, mode, trump) else -1,
                                         card_points(c, mode, trump)))
    winner_pid = trick_winner(list(table), mode, trump)
    if winner_pid % 2 == pid % 2:
        return min(legal, key=cheap)
    current = dict(table)[winner_pid]
    winners = [c for c in legal if beats(c, current, mode, trump)]
    return min(winners or legal, key=cheap)

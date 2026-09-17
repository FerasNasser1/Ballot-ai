"""Playing cards for Baloot (32-card deck, 7 through Ace)."""

from __future__ import annotations

import random
from typing import Iterable, List, Optional

SUITS = ("Spades", "Hearts", "Diamonds", "Clubs")
RANKS = ("7", "8", "9", "10", "J", "Q", "K", "A")

SUIT_SYMBOLS = {"Spades": "♠", "Hearts": "♥", "Diamonds": "♦", "Clubs": "♣"}
RED_SUITS = frozenset({"Hearts", "Diamonds"})


class Card:
    """An immutable, hashable card.

    Hashability matters: the knowledge base and the deal sampler keep cards in
    sets, which the original class could not do because it defined ``__eq__``
    without ``__hash__``.
    """

    __slots__ = ("suit", "rank")

    def __init__(self, suit: str, rank: str):
        if suit not in SUITS:
            raise ValueError(f"Unknown suit: {suit!r}")
        if rank not in RANKS:
            raise ValueError(f"Unknown rank: {rank!r}")
        object.__setattr__(self, "suit", suit)
        object.__setattr__(self, "rank", rank)

    def __setattr__(self, name, value):  # pragma: no cover - defensive
        raise AttributeError("Card is immutable")

    @property
    def symbol(self) -> str:
        return SUIT_SYMBOLS[self.suit]

    @property
    def is_red(self) -> bool:
        return self.suit in RED_SUITS

    def __repr__(self) -> str:
        return f"{self.rank}{self.symbol}"

    def __eq__(self, other) -> bool:
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))

    def __reduce__(self):
        return (Card, (self.suit, self.rank))


def full_deck() -> List[Card]:
    return [Card(s, r) for s in SUITS for r in RANKS]


def shuffled_deck(rng: Optional[random.Random] = None) -> List[Card]:
    deck = full_deck()
    (rng or random).shuffle(deck)
    return deck


def parse_card(text: str) -> Card:
    """Parse strings such as ``"10H"``, ``"JS"`` or ``"A♦"`` (handy in tests)."""
    letters = {"S": "Spades", "H": "Hearts", "D": "Diamonds", "C": "Clubs"}
    symbols = {v: k for k, v in SUIT_SYMBOLS.items()}
    text = text.strip()
    rank, suit_part = text[:-1], text[-1]
    suit = letters.get(suit_part.upper()) or symbols.get(suit_part)
    if suit is None:
        raise ValueError(f"Cannot parse card: {text!r}")
    return Card(suit, rank.upper())


def cards(text: str) -> List[Card]:
    """``cards("JH 9H AS")`` -> list of Card."""
    return [parse_card(t) for t in text.split()]


def sort_hand(hand: Iterable[Card], trump: Optional[str] = None) -> List[Card]:
    """Group by suit (trump first when known), low to high inside each suit."""
    order = list(SUITS)
    if trump in order:
        order.remove(trump)
        order.insert(0, trump)
    return sorted(hand, key=lambda c: (order.index(c.suit), RANKS.index(c.rank)))

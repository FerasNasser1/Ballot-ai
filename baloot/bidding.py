"""Mushtra (bidding).

If ``models/mushtra_model.pkl`` exists, its predictions are used. The feature
vector is identical to the original project, so a model trained for it still
works: ``[sun_points, hokom_points, cards_matching_ground_suit]``.

Without a model the original code always passed, so if the human also passed
the game redealt forever. The fallback heuristic below keeps the game playable.

The engine tells the agent which calls are legal right now (``options``). That
matters because a Hokom bid can be overcalled with Sun or Ashkal, and Ashkal is
only open to the dealer and the player on the dealer's left.

Ashkal (أشكل) is a Sun purchase where the ground card goes to the caller's
partner. The heuristic calls Ashkal when it would buy Sun anyway and the ground
card adds (almost) nothing to its own Sun strength: it then draws a fresh card
from the stock instead of a useless one.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence, Tuple

from .cards import SUITS, Card
from .rules import HOKOM, PLAIN_POINTS, SUN, TRUMP_POINTS

log = logging.getLogger(__name__)

PASS = "Pass"
BUY_SUN = "Sun"
BUY_HOKOM = "Hokom"          # round 1: trump is the ground card's suit
BUY_HOKOM_THANI = "Hokom thani"  # round 2: buyer picks another suit
BUY_ASHKAL = "Ashkal"        # Sun, but the ground card goes to the caller's partner

BUYING_ACTIONS = (BUY_SUN, BUY_HOKOM, BUY_HOKOM_THANI, BUY_ASHKAL)

_DEFAULT_PATHS = (
    Path(__file__).resolve().parent.parent / "models" / "mushtra_model.pkl",
    Path.cwd() / "models" / "mushtra_model.pkl",
    Path.cwd() / "mushtra_model.pkl",
)

HOKOM_THRESHOLD = 7.0
SUN_THRESHOLD = 7.0
ASHKAL_MAX_GAIN = 0.5   # the ground card must add less than this to our Sun strength


class MushtraEngine:
    _cached_model = None
    _load_attempted = False

    def __init__(self, model_path: Optional[str] = None, use_model: bool = True):
        self.model = self._load(model_path) if use_model else None

    @classmethod
    def _load(cls, model_path: Optional[str]):
        if model_path is None and cls._load_attempted:
            return cls._cached_model
        paths = [Path(model_path)] if model_path else list(_DEFAULT_PATHS)
        model = None
        for path in paths:
            if path.is_file():
                try:
                    import joblib  # optional dependency
                    model = joblib.load(path)
                    log.info("Loaded Mushtra model from %s", path)
                    break
                except Exception as exc:  # ImportError, unpickling errors
                    log.warning("Could not load %s (%s); using heuristic bidding", path, exc)
        if model_path is None:
            cls._cached_model, cls._load_attempted = model, True
        return model

    # -- features (unchanged from the original project) ----------------------

    @staticmethod
    def extract_features(hand: Sequence[Card], ground_card: Card):
        sun_pts = sum(PLAIN_POINTS[c.rank] for c in hand)
        hokom_pts = sum(TRUMP_POINTS[c.rank] if c.suit == ground_card.suit else PLAIN_POINTS[c.rank]
                        for c in hand)
        matching = sum(1 for c in hand if c.suit == ground_card.suit)
        return [sun_pts, hokom_pts, matching]

    # -- decision -----------------------------------------------------------

    def decide(self, hand: Sequence[Card], public_card: Card, bid_round: int,
               options: Optional[Sequence[str]] = None) -> Tuple[str, Optional[str]]:
        """Return ``(action, trump_suit)``. ``options`` are the legal calls."""
        if options is None:
            options = [PASS, BUY_SUN, BUY_HOKOM if bid_round == 1 else BUY_HOKOM_THANI]
        if self.model is not None:
            try:
                prediction = str(self.model.predict([self.extract_features(hand, public_card)])[0])
                choice = self._from_prediction(prediction, hand, public_card, bid_round, options)
            except Exception as exc:
                log.warning("Model prediction failed (%s); using heuristic", exc)
                choice = self._heuristic(hand, public_card, bid_round, options)
        else:
            choice = self._heuristic(hand, public_card, bid_round, options)
        return choice if choice[0] in options else (PASS, None)

    def _from_prediction(self, prediction, hand, public_card, bid_round, options):
        p = prediction.strip().lower()
        if p in ("suna", "sun"):
            return self._sun_or_ashkal(hand, public_card, options)
        if p == "hokom":
            if bid_round == 1:
                return BUY_HOKOM, public_card.suit
            return BUY_HOKOM_THANI, self.best_thani_suit(hand, public_card)
        return PASS, None

    def _heuristic(self, hand, public_card, bid_round, options):
        with_card = list(hand) + [public_card]  # the buyer receives the ground card
        if sun_strength(with_card) >= SUN_THRESHOLD:
            return self._sun_or_ashkal(hand, public_card, options)
        if bid_round == 1:
            if BUY_HOKOM in options and hokom_strength(with_card, public_card.suit) >= HOKOM_THRESHOLD:
                return BUY_HOKOM, public_card.suit
        elif BUY_HOKOM_THANI in options:
            suit = self.best_thani_suit(hand, public_card)
            if hokom_strength(with_card, suit) >= HOKOM_THRESHOLD:
                return BUY_HOKOM_THANI, suit
        return PASS, None

    @staticmethod
    def _sun_or_ashkal(hand, public_card, options):
        if BUY_ASHKAL in options:
            gain = sun_strength(list(hand) + [public_card]) - sun_strength(hand)
            if gain < ASHKAL_MAX_GAIN:
                return BUY_ASHKAL, None
        return BUY_SUN, None

    @staticmethod
    def best_thani_suit(hand, public_card) -> str:
        with_card = list(hand) + [public_card]
        options = [s for s in SUITS if s != public_card.suit]
        return max(options, key=lambda s: hokom_strength(with_card, s))


def hokom_strength(cards: Sequence[Card], trump: str) -> float:
    weights = {"J": 3.5, "9": 2.5, "A": 1.5, "10": 1.0}
    score = 0.0
    for c in cards:
        if c.suit == trump:
            score += weights.get(c.rank, 0.5)
        elif c.rank == "A":
            score += 1.0
        elif c.rank == "10" and Card(c.suit, "A") in cards:
            score += 0.5
    return score


def sun_strength(cards: Sequence[Card]) -> float:
    score = 0.0
    for c in cards:
        if c.rank == "A":
            score += 2.5
        elif c.rank == "10":
            score += 1.0 if Card(c.suit, "A") in cards else 0.5
        elif c.rank == "K":
            score += 0.3
    return score


__all__ = ["MushtraEngine", "PASS", "BUY_SUN", "BUY_HOKOM", "BUY_HOKOM_THANI", "BUY_ASHKAL",
           "BUYING_ACTIONS", "HOKOM", "SUN"]

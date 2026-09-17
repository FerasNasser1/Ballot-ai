"""Drive the engine with players that have no GUI (simulations and tests).

A *player* needs ``choose_bid(hand, public_card, bid_round, options)``,
``choose_escalation(view)`` and ``choose_card(view)``.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from .engine import GameEngine, Phase, RoundResult


def bid_and_double(engine: GameEngine, seats: Dict[int, object], max_redeals: int = 50) -> None:
    """Start a round and run bidding and doubling until play can begin."""
    for _ in range(max_redeals):
        engine.start_round()
        while engine.phase == Phase.BIDDING:
            pid = engine.current_bidder
            action, trump = seats[pid].choose_bid(engine.hands[pid], engine.public_card,
                                                   engine.bid_round, engine.bid_options())
            engine.apply_bid(pid, action, trump)
        if engine.phase == Phase.ROUND_OVER:
            continue        # everybody passed twice: redeal
        while engine.phase == Phase.DOUBLING:
            pid = engine.escalation_turn
            engine.apply_escalation(pid, seats[pid].choose_escalation(engine.escalation_view(pid)))
        return
    raise RuntimeError("Nobody bought after many deals")


def play_hand(engine: GameEngine, seats: Dict[int, object],
              before_play: Optional[Callable[[GameEngine], None]] = None) -> RoundResult:
    """Play one complete hand (redealing if nobody buys) and return its result.

    ``before_play`` is called before every card, which the tests use to check
    invariants mid-hand."""
    bid_and_double(engine, seats)
    while True:
        if engine.phase == Phase.TRICK_COMPLETE:
            result = engine.resolve_trick()
            if result.round_result is not None:
                return result.round_result
            continue
        if before_play is not None:
            before_play(engine)
        pid = engine.turn
        engine.play(pid, seats[pid].choose_card(engine.view_for(pid)))

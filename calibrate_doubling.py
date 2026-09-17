"""Are the doubling decisions any good?

For each dealt Hokom hand this script asks two questions and checks the answer
against what actually happens when the hand is played out:

1. *Defender.* What does the advisor think a Double is worth, and what would it
   really have been worth?
2. *Buyer.* After a Double, what does the advisor think Three is worth, and what
   was it really worth?

    python calibrate_doubling.py --hands 200

The hands are played out with the greedy policy, which favours the buying team,
so read the numbers as a comparison between the estimate and the outcome under
the same model, not as absolute truth.
"""

from __future__ import annotations

import argparse
import random
import statistics

from baloot.agent import GreedyPlayer
from baloot.engine import GameEngine, Phase
from baloot.escalation import (CALL_DOUBLE, CALL_DOUBLE_CLOSED, CALL_THREE, PASS,
                               EscalationAdvisor, play_out)
from baloot.rules import HOKOM, detect_projects, resolve_declarations, team_of
from baloot.scoring import DOUBLE, NORMAL, THREE, score_hand


def deal_hokom_hand(seed, seats):
    """Deal and bid until a Hokom hand is bought; returns the engine or None."""
    engine = GameEngine(list(seats.values()), random.Random(seed))
    engine.start_round()
    while engine.phase == Phase.BIDDING:
        pid = engine.current_bidder
        action, trump = seats[pid].choose_bid(engine.hands[pid], engine.public_card,
                                              engine.bid_round, engine.bid_options())
        engine.apply_bid(pid, action, trump)
    if engine.phase != Phase.DOUBLING or engine.mode != HOKOM:
        return None
    return engine


def outcome(engine, team, level_a, level_b):
    """Real point difference for `team` at level_a minus at level_b."""
    decl = resolve_declarations(
        {p: detect_projects(engine.hands[p], engine.mode, engine.trump) for p in range(4)}, engine.mode)
    points = play_out(engine.hands, (engine.dealer + 1) % 4, engine.mode, engine.trump, engine.locked)
    values = []
    for level in (level_a, level_b):
        hs = score_hand(engine.mode, team_of(engine.buyer), points,
                        decl.project_points, decl.baloot_points, level)
        values.append(hs.final[team] - hs.final[1 - team])
    return values[0] - values[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hands", type=int, default=200)
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    advisor = EscalationAdvisor(samples=args.samples, rng=random.Random(args.seed))
    double_est, double_real, doubles = [], [], 0
    three_est, three_real, threes = [], [], 0
    hands = 0

    for seed in range(args.hands):
        seats = {p: GreedyPlayer(p, seed=p) for p in range(4)}
        engine = deal_hokom_hand(seed, seats)
        if engine is None:
            continue
        hands += 1

        defender = engine.escalation_turn
        view = engine.escalation_view(defender)
        values = advisor.evaluate(view)
        best_double = max(values[CALL_DOUBLE], values[CALL_DOUBLE_CLOSED])
        double_est.append(best_double - values[PASS])
        double_real.append(outcome(engine, team_of(defender), DOUBLE, NORMAL))
        doubles += advisor.decide(view) != PASS

        engine.apply_escalation(defender, CALL_DOUBLE)
        view = engine.escalation_view(engine.buyer)
        values = advisor.evaluate(view)
        three_est.append(values[CALL_THREE] - values[PASS])
        three_real.append(outcome(engine, team_of(engine.buyer), THREE, DOUBLE))
        threes += advisor.decide(view) == CALL_THREE

    def report(name, est, real, chosen):
        print(f"\n{name} ({len(est)} hands)")
        print(f"  advisor's estimated gain : median {statistics.median(est):+.1f}, "
              f"mean {statistics.mean(est):+.1f}")
        print(f"  gain if it always did it : mean {statistics.mean(real):+.1f}")
        print(f"  it actually chose to     : {chosen}/{len(est)} hands ({chosen / len(est):.0%})")

    print(f"{hands} Hokom hands out of {args.hands} deals")
    if double_est:
        report("Defender: Double instead of passing", double_est, double_real, doubles)
        report("Buyer: Three after being doubled", three_est, three_real, threes)


if __name__ == "__main__":
    main()

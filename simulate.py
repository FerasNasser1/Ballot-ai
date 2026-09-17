"""Headless evaluation: how well does the AI play against simple baselines?

Examples
--------
    python simulate.py --rounds 200 --opponent greedy
    python simulate.py --rounds 100 --opponent random --samples 12 --budget 0.2
    python simulate.py --rounds 100 --opponent greedy --no-doubling

Each deal is played twice with the teams swapped between seats, using the same
random seed, so both sides get the same cards. That removes most of the luck of
the deal from the comparison. The reported number is the AI team's average
round points minus the baseline team's, with a 95% confidence interval.

Both teams bid with the same Mushtra heuristic. With doubling on, the AI team
decides Double / Three / Four / Qahwa by Monte Carlo rollouts and the baseline
team uses a hand-strength rule of thumb; ``--no-doubling`` turns all raises
off so only card play is compared. A Qahwa hand is counted as a Four (x4)
here, because a single hand has no match to win.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import time
from collections import Counter

from baloot.agent import BalootAgent, GreedyPlayer, RandomPlayer
from baloot.autoplay import play_hand
from baloot.engine import GameEngine
from baloot.escalation import PASS
from baloot.rules import team_of
from baloot.scoring import FOUR, score_hand

BASELINES = {"random": RandomPlayer, "greedy": GreedyPlayer, "ai": None}


class NoRaises:
    """Wraps a player so that it never doubles."""

    def __init__(self, player):
        self._player = player

    def __getattr__(self, name):
        return getattr(self._player, name)

    def choose_escalation(self, view):
        return PASS


def make_player(kind, pid, args, seed):
    if kind == "ai":
        player = BalootAgent(pid, samples=args.samples, time_budget=args.budget, seed=seed,
                             escalation_samples=args.escalation_samples)
    else:
        player = BASELINES[kind](pid, seed=seed)
    return NoRaises(player) if args.no_doubling else player


def play_round(seats, seed):
    """Play one hand (redealing until someone buys). Returns the RoundResult."""
    engine = GameEngine(list(seats.values()), random.Random(seed))
    return play_hand(engine, seats)


def hand_points(result):
    """Points each team earned in this hand (a Qahwa is scored as a Four)."""
    if not result.qahwa:
        return result.final
    # Recompute at x4 so a Qahwa does not dominate the average.
    baloot = result.baloot_points
    projects = [result.project_points[t] - baloot[t] for t in (0, 1)]
    return list(score_hand(result.mode, team_of(result.buyer), result.card_points,
                           projects, baloot, FOUR).final)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rounds", type=int, default=100, help="deals to play (each played twice)")
    parser.add_argument("--opponent", choices=sorted(BASELINES), default="greedy")
    parser.add_argument("--samples", type=int, default=16, help="PIMC samples per decision")
    parser.add_argument("--budget", type=float, default=0.25, help="seconds per decision")
    parser.add_argument("--escalation-samples", type=int, default=24,
                        help="Monte Carlo deals per doubling decision")
    parser.add_argument("--no-doubling", action="store_true", help="nobody may Double/Three/Four/Qahwa")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    diffs, pair_means = [], []
    raises = Counter()
    raise_outcomes = Counter()
    start = time.time()
    for i in range(args.rounds):
        seed = args.seed + i
        for ai_team in (0, 1):
            seats = {}
            for pid in range(4):
                kind = "ai" if pid % 2 == ai_team else args.opponent
                seats[pid] = make_player(kind, pid, args, seed * 10 + pid)
            result = play_round(seats, seed)
            final = hand_points(result)
            diffs.append(final[ai_team] - final[1 - ai_team])
            if result.level > 1:
                raiser_is_ai = (team_of(result.doubler) == ai_team) if result.doubler is not None else None
                who = "AI" if raiser_is_ai else "baseline"
                raises[(result.level, who)] += 1
                raise_outcomes[(who, result.winner == team_of(result.doubler))] += 1
        pair_means.append((diffs[-1] + diffs[-2]) / 2)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{args.rounds} deals, running mean {statistics.mean(diffs):+.2f}")

    # The two games of a pair share a deal, so the pair is the independent unit.
    mean = statistics.mean(pair_means)
    half_width = (1.96 * statistics.stdev(pair_means) / math.sqrt(len(pair_means))
                  if len(pair_means) > 1 else float("nan"))
    wins = sum(d > 0 for d in diffs) / len(diffs)
    print(f"\nAI vs {args.opponent}: {len(diffs)} rounds in {time.time() - start:.0f}s"
          f"{' (doubling off)' if args.no_doubling else ''}")
    print(f"Mean round-point difference: {mean:+.2f} (95% CI {mean - half_width:+.2f} to {mean + half_width:+.2f})")
    print(f"Rounds won by the AI team: {wins:.1%}")
    if raises:
        names = {2: "Double", 3: "Three", 4: "Four", 5: "Qahwa"}
        print("Raised hands (level reached, team that doubled):")
        for (level, who), n in sorted(raises.items()):
            print(f"  {names[level]:<7} doubled by {who:<8} {n}")
        for who in ("AI", "baseline"):
            won = raise_outcomes[(who, True)]
            total = won + raise_outcomes[(who, False)]
            if total:
                print(f"  Doubles by the {who} team won by the doublers: {won}/{total}")


if __name__ == "__main__":
    main()

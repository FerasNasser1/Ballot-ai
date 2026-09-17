"""Scoring a finished hand, including Double, Three, Four and Qahwa.

The procedure follows the Saudi tournament rules (Saudi Mind Sports
Federation, articles 4, 5 and 7) in the step-by-step form given by pagat.com:

1. Count each team's card points (162 in Hokum, 130 in Sun, last trick +10).
2. Only the *counting team* converts its card points to game points; the other
   team gets the rest of 16 (Hokum) or 26 (Sun). This keeps the total fixed.
   * Hokum: round to the nearest 10, a trailing 5 rounds DOWN, divide by 10.
   * Sun: round to the nearest 10 unless the last digit is 5, divide by 5.
   (Art. 4-11: "in Sun 5 card points count as one, in Hokum they count as zero".)
3. Add projects and Baloot.
4. The team with more game points wins the hand. On a tie, the team that lost
   more card points in the rounding wins; if that is also equal, the buyer's
   team wins (art. 7-6: on a tie the doubler loses).
5. Award the points:
   * Not doubled, buyer wins: each team keeps its own points.
   * Not doubled, buyer loses: the other team takes everything.
   * Double / Three / Four: the winner takes everything, card points x2/x3/x4,
     projects x2 at most, Baloot never multiplied (arts. 5-4, 5-5).
   * Qahwa (قهوة): the winner of the hand wins the whole match (art. 7-4).

Which team counts: normally the buyer's opponents. When the hand is raised,
the opponents of the *last* team to raise count (art. 4-10). So after Double or
Four the buyer's team counts, after Three or Qahwa the defenders count.

These rules reproduce every buyer-failure threshold in articles 4-2 to 4-9;
``tests/test_scoring.py`` checks all of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from .rules import HOKOM

NORMAL, DOUBLE, THREE, FOUR, QAHWA = 1, 2, 3, 4, 5

LEVEL_NAMES = {NORMAL: "", DOUBLE: "Double", THREE: "Three", FOUR: "Four", QAHWA: "Qahwa"}
LEVEL_NAMES_AR = {NORMAL: "", DOUBLE: "دبل", THREE: "ثري", FOUR: "فور", QAHWA: "قهوة"}


def base_total(mode: str) -> int:
    """Game points available for cards: 16 in Hokum, 26 in Sun."""
    return 16 if mode == HOKOM else 26


def rounding_unit(mode: str) -> int:
    return 10 if mode == HOKOM else 5


def convert_counting_points(raw: int, mode: str) -> int:
    """Convert the counting team's card points to game points."""
    if mode == HOKOM:
        return (raw + 4) // 10              # 55 -> 5, 56 -> 6
    if raw % 10 == 5:
        return raw // 5                     # 65 -> 13 (not rounded)
    return 2 * ((raw + 5) // 10)            # 64 -> 12, 66 -> 14


def raising_team(declarer_team: int, level: int) -> int:
    """The team that made the last call, which is the team that must win."""
    return 1 - declarer_team if level in (DOUBLE, FOUR) else declarer_team


def counting_team(declarer_team: int, level: int) -> int:
    return 1 - raising_team(declarer_team, level)


@dataclass(frozen=True)
class HandScore:
    game_points: Tuple[int, int]   # converted card points, sum is 16 or 26
    totals: Tuple[int, int]        # game points + projects + Baloot, before multiplying
    counting_team: int
    winner: int
    declarer_won: bool
    final: Tuple[int, int]         # what each team adds to the match score
    qahwa: bool


def score_hand(mode: str, declarer_team: int, card_points: Sequence[int],
               project_points: Sequence[int] = (0, 0), baloot_points: Sequence[int] = (0, 0),
               level: int = NORMAL) -> HandScore:
    if level not in LEVEL_NAMES:
        raise ValueError(f"Unknown level {level}")
    total_gp = base_total(mode)
    unit = rounding_unit(mode)
    c = counting_team(declarer_team, level)

    gp = [0, 0]
    gp[c] = convert_counting_points(card_points[c], mode)
    gp[1 - c] = total_gp - gp[c]
    totals = [gp[t] + project_points[t] + baloot_points[t] for t in (0, 1)]

    if totals[0] != totals[1]:
        winner = 0 if totals[0] > totals[1] else 1
    else:
        # Card points lost in rounding (negative if gained). More lost wins the tie.
        lost = [card_points[t] - unit * gp[t] for t in (0, 1)]
        if lost[0] != lost[1]:
            winner = 0 if lost[0] > lost[1] else 1
        else:
            winner = declarer_team

    projects = sum(project_points)
    baloot = sum(baloot_points)
    final = [0, 0]
    if level == NORMAL:
        if winner == declarer_team:
            final = list(totals)
        else:
            final[winner] = total_gp + projects + baloot
    else:
        mult = min(level, FOUR)
        final[winner] = total_gp * mult + projects * min(mult, 2) + baloot

    return HandScore(tuple(gp), tuple(totals), c, winner, winner == declarer_team,
                     tuple(final), level == QAHWA)

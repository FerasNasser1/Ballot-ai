"""Scoring tests taken directly from the rule sources.

* ``FederationThresholdTests`` encode articles 4-2 to 4-9 of the Saudi Mind
  Sports Federation rules: the exact number of card points at which the buyer
  loses, and the number at which the teams tie.
* ``PagatExampleTests`` encode the eight worked examples on pagat.com/jass/baloot.html.

In every test the buyer (declarer) is team 0 and the defenders are team 1.
"""

import unittest

from baloot.rules import HOKOM, SUN
from baloot.scoring import (DOUBLE, FOUR, NORMAL, QAHWA, THREE, convert_counting_points,
                            counting_team, score_hand)

HOKOM_TOTAL, SUN_TOTAL = 162, 130
SIRA_H, FIFTY_H, HUNDRED_H = 2, 5, 10
SIRA_S, FIFTY_S, HUNDRED_S = 4, 10, 20


def defenders_take(mode, raw, defender_projects=0, level=NORMAL):
    total = HOKOM_TOTAL if mode == HOKOM else SUN_TOTAL
    return score_hand(mode, 0, [total - raw, raw], [0, defender_projects], [0, 0], level)


class ConversionTests(unittest.TestCase):
    def test_hokom_trailing_five_rounds_down(self):
        self.assertEqual(convert_counting_points(55, HOKOM), 5)
        self.assertEqual(convert_counting_points(56, HOKOM), 6)
        self.assertEqual(convert_counting_points(5, HOKOM), 0)      # art. 4-11
        self.assertEqual(convert_counting_points(162, HOKOM), 16)

    def test_sun_trailing_five_is_not_rounded(self):
        self.assertEqual(convert_counting_points(64, SUN), 12)
        self.assertEqual(convert_counting_points(65, SUN), 13)
        self.assertEqual(convert_counting_points(66, SUN), 14)
        self.assertEqual(convert_counting_points(5, SUN), 1)        # art. 4-11
        self.assertEqual(convert_counting_points(130, SUN), 26)

    def test_game_points_always_sum_to_the_base(self):
        for raw in range(HOKOM_TOTAL + 1):
            self.assertEqual(sum(defenders_take(HOKOM, raw).game_points), 16)
        for raw in range(SUN_TOTAL + 1):
            self.assertEqual(sum(defenders_take(SUN, raw).game_points), 26)


class FederationThresholdTests(unittest.TestCase):
    def assert_threshold(self, mode, loses_at, ties_at, projects=0):
        lose = defenders_take(mode, loses_at, projects)
        self.assertFalse(lose.declarer_won, f"buyer should lose at {loses_at}")
        self.assertEqual(lose.final[0], 0)
        tie = defenders_take(mode, ties_at, projects)
        self.assertTrue(tie.declarer_won, f"buyer should survive at {ties_at}")

    def test_4_2_sun_no_projects(self):
        self.assert_threshold(SUN, 66, 65)
        tie = defenders_take(SUN, 65)
        self.assertEqual(tie.final, (13, 13))

    def test_4_3_hokom_no_projects(self):
        self.assert_threshold(HOKOM, 82, 81)
        self.assertEqual(defenders_take(HOKOM, 81).final, (8, 8))

    def test_4_4_sun_sira(self):
        self.assert_threshold(SUN, 56, 55, SIRA_S)

    def test_4_5_hokom_sira(self):
        self.assert_threshold(HOKOM, 72, 71, SIRA_H)

    def test_4_6_sun_fifty(self):
        self.assert_threshold(SUN, 41, 40, FIFTY_S)

    def test_4_7_hokom_fifty(self):
        self.assert_threshold(HOKOM, 56, 55, FIFTY_H)

    def test_4_8_sun_hundred(self):
        self.assert_threshold(SUN, 16, 15, HUNDRED_S)

    def test_4_9_hokom_hundred(self):
        self.assert_threshold(HOKOM, 32, 31, HUNDRED_H)

    def test_losing_buyer_gives_everything_to_the_defenders(self):
        result = score_hand(HOKOM, 0, [60, 102], [0, 0], [2, 0])
        self.assertEqual(result.final, (0, 18))    # 16 + the buyer's Baloot


class PagatExampleTests(unittest.TestCase):
    """N-S is team 0, E-W is team 1."""

    def test_example_1(self):   # E declarer, N-S count 77
        r = score_hand(HOKOM, 1, [77, 85])
        self.assertTrue(r.declarer_won)
        self.assertEqual(r.final, (8, 8))

    def test_example_2(self):   # N declarer with Baloot, E-W count 91 (and 92)
        r = score_hand(HOKOM, 0, [71, 91], baloot_points=[2, 0])
        self.assertEqual(r.final, (9, 9))
        r = score_hand(HOKOM, 0, [70, 92], baloot_points=[2, 0])
        self.assertEqual(r.final, (0, 18))

    def test_example_3(self):   # W declarer, N-S have a Fifty and 56 card points
        r = score_hand(HOKOM, 1, [56, 106], project_points=[5, 0])
        self.assertEqual(r.final, (21, 0))

    def test_example_4_double_changes_the_result(self):
        r = score_hand(HOKOM, 1, [56, 106], project_points=[5, 0], level=DOUBLE)
        self.assertEqual(r.counting_team, 1)
        self.assertEqual(r.final, (0, 42))       # 16x2 + 5x2

    def test_example_5(self):   # Sun, S declarer, E-W count 66, N-S Fifty
        r = score_hand(SUN, 0, [64, 66], project_points=[10, 0])
        self.assertEqual(r.final, (22, 14))

    def test_example_6(self):   # Sun, E-W count 55 with a Sira
        r = score_hand(SUN, 0, [75, 55], project_points=[0, 4])
        self.assertEqual(r.final, (15, 15))

    def test_example_7(self):   # Sun, E-W count 41 with a Fifty
        r = score_hand(SUN, 0, [89, 41], project_points=[0, 10])
        self.assertEqual(r.final, (0, 36))

    def test_example_8_sun_double(self):   # W declarer, S doubles, E-W take 67
        r = score_hand(SUN, 1, [63, 67], level=DOUBLE)
        self.assertEqual(r.final, (0, 52))


class EscalationScoringTests(unittest.TestCase):
    def test_counting_team_follows_the_last_raise(self):
        self.assertEqual(counting_team(0, NORMAL), 1)
        self.assertEqual(counting_team(0, DOUBLE), 0)
        self.assertEqual(counting_team(0, THREE), 1)
        self.assertEqual(counting_team(0, FOUR), 0)
        self.assertEqual(counting_team(0, QAHWA), 1)

    def test_multipliers_on_card_points(self):
        for level, expected in ((DOUBLE, 32), (THREE, 48), (FOUR, 64)):
            r = score_hand(HOKOM, 0, [100, 62], level=level)
            self.assertEqual(r.final, (expected, 0))

    def test_projects_doubled_at_most_and_baloot_never(self):
        for level, cards in ((DOUBLE, 32), (THREE, 48), (FOUR, 64)):
            r = score_hand(HOKOM, 0, [100, 62], [10, 0], [2, 0], level)
            self.assertEqual(r.final, (cards + 20 + 2, 0))

    def test_doubled_tie_goes_against_the_doubler(self):
        # Art. 7-6. 81:81 with no projects is an exact tie.
        r = score_hand(HOKOM, 0, [81, 81], level=DOUBLE)
        self.assertTrue(r.declarer_won)
        self.assertEqual(r.final, (32, 0))
        r = score_hand(SUN, 0, [65, 65], level=DOUBLE)
        self.assertEqual(r.final, (52, 0))

    def test_defenders_win_doubled_hand_outright(self):
        r = score_hand(HOKOM, 0, [60, 102], level=DOUBLE)
        self.assertEqual(r.final, (0, 32))

    def test_qahwa_marks_the_winner(self):
        r = score_hand(HOKOM, 0, [60, 102], level=QAHWA)
        self.assertTrue(r.qahwa)
        self.assertEqual(r.winner, 1)


if __name__ == "__main__":
    unittest.main()

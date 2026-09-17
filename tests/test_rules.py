import unittest

from baloot.cards import cards, parse_card as c
from baloot.rules import (HOKOM, SUN, detect_projects, legal_moves,
                          resolve_declarations, trick_winner)


class TrickWinnerTests(unittest.TestCase):
    def test_sun_highest_of_lead_suit_wins(self):
        table = [(0, c("10S")), (1, c("AS")), (2, c("AH")), (3, c("KS"))]
        self.assertEqual(trick_winner(table, SUN, None), 1)

    def test_hokom_small_trump_beats_ace(self):
        table = [(0, c("AS")), (1, c("7H")), (2, c("10S")), (3, c("KS"))]
        self.assertEqual(trick_winner(table, HOKOM, "Hearts"), 1)

    def test_hokom_trump_order_jack_then_nine(self):
        table = [(0, c("AH")), (1, c("9H")), (2, c("JH")), (3, c("10H"))]
        self.assertEqual(trick_winner(table, HOKOM, "Hearts"), 2)

    def test_non_trump_uses_ten_above_king(self):
        table = [(0, c("KD")), (1, c("10D")), (2, c("QD")), (3, c("7D"))]
        self.assertEqual(trick_winner(table, HOKOM, "Hearts"), 1)


class LegalMoveTests(unittest.TestCase):
    def test_must_follow_suit(self):
        hand = cards("7S AH KH")
        self.assertEqual(legal_moves(hand, [(0, c("AS"))], SUN, None), cards("7S"))

    def test_void_in_sun_plays_anything(self):
        hand = cards("AH KD")
        self.assertEqual(set(legal_moves(hand, [(0, c("AS"))], SUN, None)), set(hand))

    def test_hokom_must_overtrump_when_trump_led(self):
        hand = cards("7H 9H JH")
        moves = legal_moves(hand, [(0, c("AH"))], HOKOM, "Hearts")
        self.assertEqual(set(moves), set(cards("9H JH")))

    def test_hokom_void_must_trump_when_opponent_winning(self):
        hand = cards("7H AD")
        self.assertEqual(legal_moves(hand, [(0, c("AS"))], HOKOM, "Hearts"), cards("7H"))

    def test_hokom_void_free_when_partner_winning(self):
        hand = cards("7H AD")
        table = [(0, c("AS")), (1, c("7S"))]  # seat 2's partner (seat 0) is winning
        self.assertEqual(set(legal_moves(hand, table, HOKOM, "Hearts")), set(hand))

    def test_hokom_void_must_overtrump_if_possible(self):
        hand = cards("7H JH AD")
        table = [(0, c("AS")), (1, c("9H"))]
        self.assertEqual(legal_moves(hand, table, HOKOM, "Hearts"), cards("JH"))

    def test_hokom_void_cannot_overtrump_still_plays_trump(self):
        hand = cards("7H 8H AD")
        table = [(0, c("AS")), (1, c("9H"))]
        self.assertEqual(set(legal_moves(hand, table, HOKOM, "Hearts")), set(cards("7H 8H")))


class ProjectTests(unittest.TestCase):
    def test_sequences(self):
        hand = cards("7S 8S 9S JH QH KH AH 10D")
        self.assertEqual(sorted(p.name for p in detect_projects(hand, SUN)), ["50", "Sira"])

    def test_two_runs_in_one_suit(self):
        hand = cards("7S 8S 9S JS QS KS AD 10D")
        self.assertEqual([p.name for p in detect_projects(hand, SUN)], ["Sira", "Sira"])

    def test_four_aces(self):
        hand = cards("AS AH AD AC 7S 9H JD QC")
        self.assertEqual(detect_projects(hand, SUN)[0].name, "400")
        hokom = detect_projects(hand, HOKOM, "Hearts")
        self.assertEqual(hokom[0].name, "100")
        self.assertEqual(hokom[0].points(HOKOM), 10)

    def test_baloot(self):
        hand = cards("KH QH 7S 9D JC 10S 8D AC")
        self.assertEqual([p.name for p in detect_projects(hand, HOKOM, "Hearts")], ["Baloot"])

    def test_only_best_team_scores(self):
        projects = {
            0: detect_projects(cards("7S 8S 9S 10S AH KD QC JC"), SUN),  # 50
            1: detect_projects(cards("7H 8H 9H AS KS QD 10C JD"), SUN),  # Sira
            2: [], 3: [],
        }
        result = resolve_declarations(projects, SUN)
        self.assertEqual(result.winning_team, 0)
        self.assertEqual(result.team_points, [10, 0])
        self.assertIn(0, result.shown)
        self.assertNotIn(1, result.shown)

    def test_baloot_always_scores(self):
        projects = {
            0: detect_projects(cards("7S 8S 9S 10S AH KD QC JC"), HOKOM, "Hearts"),
            1: detect_projects(cards("KH QH 7D AS KS 9D 10C JD"), HOKOM, "Hearts"),
            2: [], 3: [],
        }
        self.assertEqual(resolve_declarations(projects, HOKOM).team_points, [5, 2])


if __name__ == "__main__":
    unittest.main()

"""Double, Three, Four, Qahwa and closed play."""

import random
import unittest
from dataclasses import replace

from baloot.agent import BalootAgent
from baloot.bidding import BUY_HOKOM, BUY_SUN, PASS
from baloot.cards import SUITS, Card, cards, parse_card as c
from baloot.engine import GameEngine, IllegalAction, Phase
from baloot.escalation import (CALL_DOUBLE, CALL_DOUBLE_CLOSED, CALL_FOUR, CALL_FOUR_CLOSED,
                               CALL_QAHWA, CALL_THREE, EscalationAdvisor, sun_double_allowed)
from baloot.rules import HOKOM, SUN, legal_moves, team_of
from baloot.scoring import DOUBLE, FOUR, NORMAL, QAHWA, THREE


def bought(mode, totals=(0, 0), seed=5):
    """An engine where the first bidder has just bought ``mode``."""
    e = GameEngine(rng=random.Random(seed))
    e.totals = list(totals)
    e.start_round()
    e.apply_bid(e.current_bidder, BUY_HOKOM if mode == HOKOM else BUY_SUN)
    while e.phase == Phase.BIDDING:
        e.apply_bid(e.current_bidder, PASS)
    return e


class HokomEscalationTests(unittest.TestCase):
    def test_defenders_are_asked_in_order(self):
        e = bought(HOKOM)
        self.assertEqual(e.phase, Phase.DOUBLING)
        defenders = [p for p in e.bid_order if team_of(p) != team_of(e.buyer)]
        self.assertEqual(e.escalation_turn, defenders[0])
        self.assertEqual(e.escalation_options(), [PASS, CALL_DOUBLE, CALL_DOUBLE_CLOSED])
        self.assertEqual(e.apply_escalation(defenders[0], PASS), "pass")
        self.assertEqual(e.escalation_turn, defenders[1])
        self.assertEqual(e.apply_escalation(defenders[1], PASS), "done")
        self.assertEqual((e.phase, e.level, e.locked), (Phase.PLAYING, NORMAL, False))

    def test_full_ladder_between_buyer_and_doubler(self):
        e = bought(HOKOM)
        doubler = e.escalation_turn
        self.assertEqual(e.apply_escalation(doubler, CALL_DOUBLE_CLOSED), "raised")
        self.assertEqual((e.level, e.locked, e.doubler), (DOUBLE, True, doubler))
        self.assertEqual(e.escalation_turn, e.buyer)
        self.assertEqual(e.escalation_options(), [PASS, CALL_THREE])

        e.apply_escalation(e.buyer, CALL_THREE)
        self.assertEqual((e.level, e.locked), (THREE, False))      # Three is always open
        self.assertEqual(e.escalation_turn, doubler)
        self.assertEqual(e.escalation_options(), [PASS, CALL_FOUR, CALL_FOUR_CLOSED])

        e.apply_escalation(doubler, CALL_FOUR_CLOSED)
        self.assertEqual((e.level, e.locked), (FOUR, True))
        self.assertEqual(e.escalation_turn, e.buyer)
        self.assertEqual(e.escalation_options(), [PASS, CALL_QAHWA])

        self.assertEqual(e.apply_escalation(e.buyer, CALL_QAHWA), "done")
        self.assertEqual((e.level, e.locked, e.phase), (QAHWA, False, Phase.PLAYING))

    def test_buyers_partner_cannot_answer_a_double(self):
        e = bought(HOKOM)
        e.apply_escalation(e.escalation_turn, CALL_DOUBLE)
        with self.assertRaises(IllegalAction):
            e.apply_escalation((e.buyer + 2) % 4, CALL_THREE)

    def test_second_defender_can_double_after_first_passes(self):
        e = bought(HOKOM)
        first = e.escalation_turn
        e.apply_escalation(first, PASS)
        second = e.escalation_turn
        e.apply_escalation(second, CALL_DOUBLE)
        self.assertEqual(e.doubler, second)

    def test_buyer_passing_ends_the_ladder(self):
        e = bought(HOKOM)
        e.apply_escalation(e.escalation_turn, CALL_DOUBLE)
        self.assertEqual(e.apply_escalation(e.buyer, PASS), "done")
        self.assertEqual((e.level, e.phase), (DOUBLE, Phase.PLAYING))


class SunEscalationTests(unittest.TestCase):
    def test_sun_double_rule(self):
        self.assertTrue(sun_double_allowed((120, 100), 0))
        self.assertFalse(sun_double_allowed((100, 90), 0))     # buyers must be above 100
        self.assertFalse(sun_double_allowed((120, 101), 0))    # defenders must be 100 or less
        self.assertFalse(sun_double_allowed((50, 130), 0))

    def test_no_doubling_phase_when_not_allowed(self):
        e = bought(SUN, totals=(0, 0))
        self.assertEqual(e.phase, Phase.PLAYING)

    def test_sun_double_only_and_no_lock(self):
        e = GameEngine(rng=random.Random(5))
        e.start_round()
        buyer = e.current_bidder
        e.totals = [0, 0]
        e.totals[team_of(buyer)] = 120
        e.totals[1 - team_of(buyer)] = 40
        e.apply_bid(buyer, BUY_SUN)
        self.assertEqual(e.phase, Phase.DOUBLING)
        self.assertEqual(e.escalation_options(), [PASS, CALL_DOUBLE])
        self.assertEqual(e.apply_escalation(e.escalation_turn, CALL_DOUBLE), "done")
        self.assertEqual((e.level, e.locked, e.phase), (DOUBLE, False, Phase.PLAYING))


class ClosedPlayTests(unittest.TestCase):
    def test_closed_game_forbids_trump_lead(self):
        hand = cards("JH 9H AS 7D")
        self.assertEqual(set(legal_moves(hand, [], HOKOM, "Hearts", locked=True)), set(cards("AS 7D")))
        self.assertEqual(set(legal_moves(hand, [], HOKOM, "Hearts", locked=False)), set(hand))

    def test_all_trump_hand_may_lead_trump(self):
        hand = cards("JH 9H")
        self.assertEqual(set(legal_moves(hand, [], HOKOM, "Hearts", locked=True)), set(hand))

    def test_closed_does_not_change_following(self):
        hand = cards("7H JH AD")
        table = [(0, c("AS")), (1, c("9H"))]
        self.assertEqual(legal_moves(hand, table, HOKOM, "Hearts", locked=True), cards("JH"))


class AdvisorTests(unittest.TestCase):
    def test_advisor_returns_a_legal_call(self):
        e = bought(HOKOM, seed=11)
        pid = e.escalation_turn
        advisor = EscalationAdvisor(samples=6, rng=random.Random(0))
        view = e.escalation_view(pid)
        self.assertIn(advisor.decide(view), view.options)

    def test_advisor_doubles_a_crushing_trump_hand(self):
        e = bought(HOKOM, seed=11)
        pid = e.escalation_turn
        trump, ground = e.trump, e.public_card
        wanted = [Card(trump, r) for r in ("J", "9", "A", "10", "K")]
        wanted += [Card(s, r) for s in SUITS if s != trump for r in ("A", "10")]
        hand = tuple([card for card in wanted if card != ground][:8])
        self.assertEqual(len(hand), 8)
        view = replace(e.escalation_view(pid), hand=hand)
        values = EscalationAdvisor(samples=30, rng=random.Random(1)).evaluate(view)
        self.assertGreater(values[CALL_DOUBLE_CLOSED], values[PASS])
        self.assertGreater(values[CALL_DOUBLE], values[PASS])

    def test_advisor_passes_with_a_weak_hand(self):
        e = bought(HOKOM, seed=11)
        pid = e.escalation_turn
        trump, ground = e.trump, e.public_card
        weak = [Card(s, r) for s in SUITS if s != trump for r in ("7", "8", "9")]
        hand = tuple([card for card in weak if card != ground][:8])
        view = replace(e.escalation_view(pid), hand=hand)
        self.assertEqual(EscalationAdvisor(samples=30, rng=random.Random(2)).decide(view), PASS)

    def test_agent_uses_advisor(self):
        e = bought(HOKOM, seed=11)
        pid = e.escalation_turn
        agent = BalootAgent(pid, samples=2, time_budget=0.01, seed=1, escalation_samples=4)
        self.assertIn(agent.choose_escalation(e.escalation_view(pid)), e.escalation_options())


if __name__ == "__main__":
    unittest.main()

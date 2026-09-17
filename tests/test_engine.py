import random
import unittest

from baloot.agent import BalootAgent, GreedyPlayer, RandomPlayer
from baloot.autoplay import play_hand
from baloot.bidding import BUY_ASHKAL, BUY_HOKOM, BUY_HOKOM_THANI, BUY_SUN, PASS
from baloot.engine import TARGET_SCORE, GameEngine, IllegalAction, Phase
from baloot.rules import HOKOM, SUN, total_card_points
from baloot.scoring import NORMAL


class EngineTests(unittest.TestCase):
    def test_points_add_up_and_scores_are_consistent(self):
        for seed in range(15):
            seats = {p: GreedyPlayer(p, seed=p) for p in range(4)}
            engine = GameEngine(list(seats.values()), random.Random(seed))
            result = play_hand(engine, seats)
            self.assertEqual(sum(result.card_points), total_card_points(result.mode))
            self.assertEqual(sum(result.base), 16 if result.mode == HOKOM else 26)
            if result.level == NORMAL and not result.buyer_failed:
                self.assertEqual(sum(result.final), sum(result.base) + sum(result.project_points))
            if result.buyer_failed or result.level != NORMAL:
                self.assertEqual(result.final[1 - result.winner], 0)

    def test_agents_complete_a_round(self):
        seats = {p: BalootAgent(p, samples=4, time_budget=0.05, seed=p, escalation_samples=6)
                 for p in range(4)}
        engine = GameEngine(list(seats.values()), random.Random(3))
        self.assertIn(play_hand(engine, seats).mode, (HOKOM, SUN))

    def test_random_calls_reach_every_level_and_matches_finish(self):
        levels = set()
        for seed in range(40):
            seats = {p: RandomPlayer(p, seed=seed * 7 + p, random_calls=True) for p in range(4)}
            engine = GameEngine(list(seats.values()), random.Random(seed))
            while engine.phase != Phase.MATCH_OVER:
                result = play_hand(engine, seats)
                levels.add(result.level)
                if result.qahwa:
                    self.assertEqual(engine.phase, Phase.MATCH_OVER)
                    self.assertEqual(engine.match_winner, result.winner)
                    self.assertEqual(engine.totals[result.winner], max(engine.totals))
                    self.assertGreaterEqual(engine.totals[result.winner], TARGET_SCORE)
        self.assertEqual(levels, {1, 2, 3, 4, 5})


class BiddingTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(rng=random.Random(1))
        self.engine.start_round()
        e = self.engine
        self.first, self.second, self.left, self.dealer = e.bid_order

    def bid(self, action, trump=None):
        return self.engine.apply_bid(self.engine.current_bidder, action, trump)

    def test_bidding_order_starts_right_of_dealer(self):
        e = self.engine
        self.assertEqual(e.bid_order, [(e.dealer + i) % 4 for i in (1, 2, 3, 4)])
        self.assertEqual(self.left, (e.dealer + 3) % 4)

    def test_rejects_out_of_turn_bid(self):
        with self.assertRaises(IllegalAction):
            self.engine.apply_bid(self.second, PASS)

    def test_thani_requires_other_suit(self):
        for _ in range(4):
            self.bid(PASS)
        with self.assertRaises(IllegalAction):
            self.bid(BUY_HOKOM_THANI, self.engine.public_card.suit)

    def test_everyone_passing_twice_redeals(self):
        outcomes = [self.bid(PASS) for _ in range(8)]
        self.assertEqual(outcomes[3], "second_round")
        self.assertEqual(outcomes[-1], "redeal")

    def test_hokom_stands_when_nobody_overcalls(self):
        self.bid(PASS)
        self.assertEqual(self.bid(BUY_HOKOM), "hokom")
        # first (who passed), left and dealer each get one chance to take Sun
        self.assertEqual([self.engine.current_bidder], [self.first])
        for _ in range(2):
            self.assertEqual(self.bid(PASS), "pass")
        self.assertEqual(self.bid(PASS), "bought")
        self.assertEqual((self.engine.mode, self.engine.buyer), (HOKOM, self.second))
        self.assertEqual(self.engine.trump, self.engine.public_card.suit)

    def test_sun_overcalls_hokom_even_after_passing(self):
        self.bid(PASS)
        self.bid(BUY_HOKOM)
        self.assertNotIn(BUY_HOKOM, self.engine.bid_options())
        self.assertEqual(self.bid(BUY_SUN), "bought")
        self.assertEqual((self.engine.mode, self.engine.buyer), (SUN, self.first))

    def test_ashkal_only_for_dealer_and_dealers_left(self):
        e = self.engine
        self.assertNotIn(BUY_ASHKAL, e.bid_options())      # first
        self.bid(PASS)
        self.assertNotIn(BUY_ASHKAL, e.bid_options())      # dealer's partner
        self.bid(PASS)
        self.assertIn(BUY_ASHKAL, e.bid_options())         # dealer's left
        self.bid(PASS)
        self.assertIn(BUY_ASHKAL, e.bid_options())         # dealer

    def test_ashkal_gives_ground_card_to_partner(self):
        e = self.engine
        ground = e.public_card
        for _ in range(3):
            self.bid(PASS)
        self.assertEqual(self.bid(BUY_ASHKAL), "bought")
        self.assertEqual(e.mode, SUN)
        self.assertTrue(e.ashkal)
        self.assertEqual(e.buyer, self.dealer)
        self.assertEqual(e.taker, self.second)             # the dealer's partner
        self.assertIn(ground, e.hands[self.second])
        self.assertNotIn(ground, e.hands[self.dealer])
        self.assertTrue(all(len(h) == 8 for h in e.hands.values()))

    def test_ashkal_can_overcall_hokom(self):
        self.bid(BUY_HOKOM)                 # first bids Hokom
        self.bid(PASS)                      # second
        self.assertEqual(self.bid(BUY_ASHKAL), "bought")   # dealer's left
        self.assertEqual((self.engine.buyer, self.engine.taker), (self.left, self.first))

    def test_ashkal_in_second_round(self):
        for _ in range(6):
            self.bid(PASS)
        self.assertIn(BUY_ASHKAL, self.engine.bid_options())
        self.assertEqual(self.bid(BUY_ASHKAL), "bought")

    def test_passed_player_cannot_return_in_second_round(self):
        for _ in range(4):
            self.bid(PASS)
        self.bid(PASS)                                      # first says wala
        suit = self.engine.thani_suits()[0]
        self.assertEqual(self.bid(BUY_HOKOM_THANI, suit), "hokom")
        self.assertEqual(self.engine.current_bidder, self.left)
        self.bid(PASS)
        self.assertEqual(self.bid(PASS), "bought")
        self.assertEqual((self.engine.mode, self.engine.trump, self.engine.buyer),
                         (HOKOM, suit, self.second))

    def test_strict_federation_ashkal_needs_opponent_hokom(self):
        e = GameEngine(rng=random.Random(1), ashkal_requires_hokom=True)
        e.start_round()
        first, second, left, dealer = e.bid_order
        e.apply_bid(first, PASS)
        e.apply_bid(second, PASS)
        self.assertNotIn(BUY_ASHKAL, e.bid_options())       # nobody bought Hokom
        e.apply_bid(left, PASS)
        e.apply_bid(dealer, BUY_HOKOM)
        # Overcall round: first, second, left. Left is the dealer's opponent.
        e.apply_bid(first, PASS)
        e.apply_bid(second, PASS)
        self.assertIn(BUY_ASHKAL, e.bid_options())

        e2 = GameEngine(rng=random.Random(1), ashkal_requires_hokom=True)
        e2.start_round()
        first, second, left, dealer = e2.bid_order
        e2.apply_bid(first, PASS)
        e2.apply_bid(second, BUY_HOKOM)      # the dealer's own partner
        e2.apply_bid(first, PASS)
        e2.apply_bid(left, PASS)
        self.assertNotIn(BUY_ASHKAL, e2.bid_options())      # dealer: partner's Hokom


if __name__ == "__main__":
    unittest.main()

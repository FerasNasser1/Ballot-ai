"""The knowledge base must never contradict the real deal, and the sampler
must only produce deals that satisfy it."""

import random
import unittest

from baloot.agent import RandomPlayer
from baloot.autoplay import play_hand
from baloot.cards import cards, parse_card as c
from baloot.engine import GameEngine, Phase
from baloot.knowledge import KnowledgeBase
from baloot.rules import HOKOM, SUN
from baloot.sampler import DealSampler


class InferenceTests(unittest.TestCase):
    def test_r1_void_in_lead_suit(self):
        kb = KnowledgeBase(0)
        kb.observe_play(2, c("AH"), [(1, c("7S"))], SUN, None)
        self.assertIn("Spades", kb.voids[2])

    def test_r2_void_in_trump(self):
        kb = KnowledgeBase(0)
        kb.observe_play(2, c("7D"), [(1, c("AS"))], HOKOM, "Hearts")
        self.assertEqual(kb.voids[2], {"Spades", "Hearts"})

    def test_r2_not_applied_when_partner_winning(self):
        kb = KnowledgeBase(0)
        kb.observe_play(3, c("7D"), [(1, c("AS")), (2, c("7S"))], HOKOM, "Hearts")
        self.assertEqual(kb.voids[3], {"Spades"})

    def test_r3_no_higher_trump(self):
        kb = KnowledgeBase(0)
        kb.observe_play(2, c("7H"), [(1, c("AH"))], HOKOM, "Hearts")
        self.assertEqual(kb.excluded[2], set(cards("9H JH")))

    def test_r6_ground_card_is_with_its_taker(self):
        kb = KnowledgeBase(0)
        kb.observe_contract(HOKOM, "Hearts", False, 3, c("KH"))
        self.assertEqual(kb.known[3], {c("KH")})
        kb.observe_play(3, c("KH"), [], HOKOM, "Hearts")
        self.assertEqual(kb.known[3], set())

    def test_r6_not_applied_to_own_hand(self):
        kb = KnowledgeBase(1)
        kb.observe_contract(SUN, None, False, 1, c("AS"))
        self.assertEqual(kb.known[1], set())

    def test_r7_trump_lead_in_closed_game_means_only_trumps(self):
        kb = KnowledgeBase(0)
        kb.observe_contract(HOKOM, "Hearts", True, 1, c("7C"))
        kb.observe_play(2, c("9H"), [], HOKOM, "Hearts")
        self.assertEqual(kb.voids[2], {"Spades", "Diamonds", "Clubs"})

    def test_r7_not_applied_in_open_game(self):
        kb = KnowledgeBase(0)
        kb.observe_contract(HOKOM, "Hearts", False, 1, c("7C"))
        kb.observe_play(2, c("9H"), [], HOKOM, "Hearts")
        self.assertEqual(kb.voids[2], set())

    def test_r4_and_r5_declared_cards(self):
        kb = KnowledgeBase(0)
        kb.observe_declaration(1, cards("7S 8S 9S"))
        self.assertEqual(kb.known[1], set(cards("7S 8S 9S")))
        kb.observe_play(1, c("8S"), [], SUN, None)
        self.assertEqual(kb.known[1], set(cards("7S 9S")))


class SoundnessTests(unittest.TestCase):
    """Over complete hands, including doubled and closed ones, every knowledge
    base must agree with the real deal, and every sample must satisfy it."""

    def test_knowledge_and_samples_match_real_games(self):
        rng = random.Random(7)
        closed_hands = 0
        for game in range(24):
            seats = {p: RandomPlayer(p, seed=game * 10 + p, random_calls=True) for p in range(4)}
            kbs = {p: KnowledgeBase(p) for p in range(4)}

            class Mirror:
                def __getattr__(self, name):
                    return lambda *args: [getattr(kb, name if name != "new_round" else "reset")(*args)
                                          for kb in kbs.values()]

            def check(engine):
                for p, kb in kbs.items():
                    self.assertTrue(kb.consistent_with(engine.hands), kb.describe())
                    sample = DealSampler(kb, engine.hands[p], rng).sample()
                    self.assertTrue(kb.consistent_with(sample))

            engine = GameEngine([Mirror()], random.Random(game))
            result = play_hand(engine, seats, before_play=check)
            closed_hands += result.locked
        self.assertGreater(closed_hands, 0, "the test should cover closed hands")


if __name__ == "__main__":
    unittest.main()

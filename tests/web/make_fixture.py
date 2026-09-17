"""Record what the Python engine does, so the JavaScript port can be checked
against it.

    python tests/web/make_fixture.py

writes ``tests/web/fixture.json``: unit cases for the rules and the scoring,
plus complete hands (deal, every call, every card, the knowledge base after each
trick, and the final score). ``tests/web/core.test.js`` replays them through
``docs/baloot.js`` and fails if anything differs.
"""

from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from baloot.bidding import MushtraEngine, PASS
from baloot.cards import RANKS, SUITS, Card, full_deck
from baloot.engine import GameEngine, Phase
from baloot.knowledge import KnowledgeBase
from baloot.policies import greedy_card
from baloot.rules import HOKOM, SUN, detect_projects, legal_moves, resolve_declarations, trick_winner
from baloot.scoring import score_hand

SUIT_LETTER = {"Spades": "S", "Hearts": "H", "Diamonds": "D", "Clubs": "C"}
OUT = os.path.join(os.path.dirname(__file__), "fixture.json")


def code(card: Card) -> str:
    return f"{card.rank}{SUIT_LETTER[card.suit]}"


def codes(cards):
    return [code(c) for c in cards]


def table_codes(table):
    return [[pid, code(card)] for pid, card in table]


def kb_state(kb: KnowledgeBase):
    return {
        "voids": [sorted(SUIT_LETTER[s] for s in kb.voids[p]) for p in range(4)],
        "known": [sorted(codes(kb.known[p])) for p in range(4)],
        "excluded": [sorted(codes(kb.excluded[p])) for p in range(4)],
        "playedBy": list(kb.played_by),
        "locked": kb.locked,
    }


def rules_cases(rng, n=400):
    cases = []
    deck = full_deck()
    while len(cases) < n:
        shuffled = deck[:]
        rng.shuffle(shuffled)
        hand = shuffled[:rng.randint(1, 8)]
        table_size = rng.randint(0, 3)
        table = [((i + 1) % 4, shuffled[8 + i]) for i in range(table_size)]
        if table and any(c in hand for _, c in table):
            continue
        mode = rng.choice([HOKOM, SUN])
        trump = rng.choice(SUITS) if mode == HOKOM else None
        locked = rng.random() < 0.4
        moves = legal_moves(hand, table, mode, trump, locked)
        case = {
            "hand": codes(hand), "table": table_codes(table), "mode": mode,
            "trump": SUIT_LETTER[trump] if trump else None, "locked": locked,
            "legal": sorted(codes(moves)),
        }
        if len(table) == 3:
            case["winnerOfFullTrick"] = trick_winner(table + [(0, hand[0])], mode, trump) \
                if hand[0] not in [c for _, c in table] else None
        cases.append(case)
    return cases


def project_cases(rng, n=150):
    cases = []
    deck = full_deck()
    for _ in range(n):
        shuffled = deck[:]
        rng.shuffle(shuffled)
        hands = {p: shuffled[p * 8:(p + 1) * 8] for p in range(4)}
        mode = rng.choice([HOKOM, SUN])
        trump = rng.choice(SUITS) if mode == HOKOM else None
        projects = {p: detect_projects(hands[p], mode, trump) for p in range(4)}
        decl = resolve_declarations(projects, mode)
        cases.append({
            "hands": {str(p): codes(hands[p]) for p in range(4)},
            "mode": mode, "trump": SUIT_LETTER[trump] if trump else None,
            "projects": {str(p): sorted(x.name for x in projects[p]) for p in range(4)},
            "winningTeam": decl.winning_team,
            "teamPoints": list(decl.team_points),
            "projectPoints": list(decl.project_points),
            "balootPoints": list(decl.baloot_points),
        })
    return cases


def scoring_cases(rng, n=600):
    cases = []
    for _ in range(n):
        mode = rng.choice([HOKOM, SUN])
        total = 162 if mode == HOKOM else 130
        a = rng.randint(0, total)
        card_points = [a, total - a]
        projects = [rng.choice([0, 0, 2, 4, 5, 10, 20]), rng.choice([0, 0, 2, 4, 5, 10])]
        if projects[0] and projects[1]:
            projects[rng.randint(0, 1)] = 0        # only one team scores projects
        baloots = [rng.choice([0, 0, 2]), 0] if mode == HOKOM else [0, 0]
        declarer_team = rng.randint(0, 1)
        level = rng.choice([1, 1, 2, 3, 4, 5])
        hs = score_hand(mode, declarer_team, card_points, projects, baloots, level)
        cases.append({
            "mode": mode, "declarerTeam": declarer_team, "cardPoints": card_points,
            "projects": projects, "baloots": baloots, "level": level,
            "gamePoints": list(hs.game_points), "totals": list(hs.totals),
            "countingTeam": hs.counting_team, "winner": hs.winner,
            "declarerWon": hs.declarer_won, "final": list(hs.final), "qahwa": hs.qahwa,
        })
    return cases


def record_hand(seed: int, dealer: int, rng: random.Random):
    """Play one hand with fixed, reproducible choices and record everything."""
    deck = full_deck()
    rng.shuffle(deck)
    bidder = MushtraEngine(use_model=False)
    kbs = {p: KnowledgeBase(p) for p in range(4)}

    class Mirror:
        def new_round(self):
            for kb in kbs.values():
                kb.reset()

        def observe_contract(self, *args):
            for kb in kbs.values():
                kb.observe_contract(*args)

        def observe_play(self, *args):
            for kb in kbs.values():
                kb.observe_play(*args)

        def observe_declaration(self, *args):
            for kb in kbs.values():
                kb.observe_declaration(*args)

    engine = GameEngine([Mirror()], random.Random(seed))
    engine.dealer = (dealer - 1) % 4
    engine.start_round()
    engine.hands = {p: deck[p * 5:(p + 1) * 5] for p in range(4)}
    engine.public_card = deck[20]
    engine._stock = deck[21:]

    steps = []
    while engine.phase == Phase.BIDDING:
        pid = engine.current_bidder
        options = engine.bid_options()
        action, trump = bidder.decide(engine.hands[pid], engine.public_card, engine.bid_round, options)
        steps.append({"type": "bid", "pid": pid, "options": sorted(options),
                      "action": action, "trump": SUIT_LETTER[trump] if trump else None})
        engine.apply_bid(pid, action, trump)
    if engine.phase == Phase.ROUND_OVER:
        return None                       # everybody passed twice

    while engine.phase == Phase.DOUBLING:
        pid = engine.escalation_turn
        options = engine.escalation_options()
        action = rng.choice(options) if rng.random() < 0.6 else PASS
        steps.append({"type": "call", "pid": pid, "options": list(options), "action": action})
        engine.apply_escalation(pid, action)

    while engine.phase in (Phase.PLAYING, Phase.TRICK_COMPLETE):
        if engine.phase == Phase.TRICK_COMPLETE:
            result = engine.resolve_trick()
            steps.append({"type": "trick", "winner": result.winner, "points": result.points,
                          "kb1": kb_state(kbs[1])})
            if result.round_result is not None:
                r = result.round_result
                return {
                    "deck": codes(deck), "dealer": dealer, "steps": steps,
                    "result": {
                        "mode": r.mode, "trump": SUIT_LETTER[r.trump] if r.trump else None,
                        "buyer": r.buyer, "ashkal": r.ashkal, "level": r.level, "locked": r.locked,
                        "cardPoints": r.card_points, "base": r.base,
                        "projectPoints": r.project_points, "final": r.final,
                        "winner": r.winner, "buyerFailed": r.buyer_failed, "qahwa": r.qahwa,
                        "totalsAfter": r.totals_after,
                    },
                }
            continue
        pid = engine.turn
        legal = engine.legal_moves(pid)
        card = greedy_card(pid, engine.hands[pid], engine.table, engine.mode, engine.trump, engine.locked)
        steps.append({"type": "play", "pid": pid, "legal": sorted(codes(legal)), "card": code(card)})
        engine.play(pid, card)


def main():
    rng = random.Random(20260918)
    hands = []
    seed = 0
    while len(hands) < 30:
        recorded = record_hand(seed, seed % 4, rng)
        seed += 1
        if recorded is not None:
            hands.append(recorded)
    fixture = {
        "rules": rules_cases(random.Random(1)),
        "projects": project_cases(random.Random(2)),
        "scoring": scoring_cases(random.Random(3)),
        "hands": hands,
    }
    with open(OUT, "w") as handle:
        json.dump(fixture, handle)
    levels = sorted({h["result"]["level"] for h in hands})
    print(f"wrote {OUT}: {len(fixture['rules'])} rules cases, {len(fixture['projects'])} project cases, "
          f"{len(fixture['scoring'])} scoring cases, {len(hands)} hands (levels {levels})")


if __name__ == "__main__":
    main()

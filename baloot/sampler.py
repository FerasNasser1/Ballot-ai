"""Sample hidden hands that are consistent with the knowledge base.

This is a genuine constraint satisfaction problem:

* Variables:   every card whose location is unknown to the agent.
* Domains:     the other three players.
* Constraints: void suits (R1, R2), excluded trumps (R3), cards already known
               to be in a hand (R4), and each player's exact hand size.

It is solved with randomized backtracking search, using the minimum remaining
values (MRV) heuristic to pick the next card and forward checking on hand
capacities. Randomizing the value order gives a different consistent deal on
each call. The samples are not perfectly uniform over all consistent deals,
which is an accepted approximation for Monte Carlo sampling.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from .cards import Card, full_deck
from .knowledge import KnowledgeBase


class DealSampler:
    def __init__(self, kb: KnowledgeBase, my_hand: Sequence[Card],
                 rng: Optional[random.Random] = None, node_limit: int = 5000):
        self.kb = kb
        self.me = kb.my_id
        self.my_hand = list(my_hand)
        self.rng = rng or random.Random()
        self.node_limit = node_limit
        self.others = [p for p in range(4) if p != self.me]

        hidden = set(self.my_hand) | kb.played
        for p in self.others:
            hidden |= kb.known[p]
        self.unknown = [c for c in full_deck() if c not in hidden]

    def sample(self) -> Optional[Dict[int, List[Card]]]:
        deal = self._solve(use_exclusions=True)
        if deal is None:
            # Only reachable if the node limit is hit; relax the weakest rule.
            deal = self._solve(use_exclusions=False)
        if deal is None:
            deal = self._fill_by_size_only()
        if deal is not None:
            deal[self.me] = list(self.my_hand)
        return deal

    # -- CSP ----------------------------------------------------------------

    def _solve(self, use_exclusions: bool) -> Optional[Dict[int, List[Card]]]:
        kb = self.kb
        hands = {p: list(kb.known[p]) for p in self.others}
        capacity = {p: kb.cards_in_hand(p) - len(hands[p]) for p in self.others}
        if any(v < 0 for v in capacity.values()) or sum(capacity.values()) != len(self.unknown):
            return None

        def allowed(p: int, c: Card) -> bool:
            if c.suit in kb.voids[p]:
                return False
            return not (use_exclusions and c in kb.excluded[p])

        domains = {c: [p for p in self.others if allowed(p, c)] for c in self.unknown}
        unassigned = list(self.unknown)
        self.rng.shuffle(unassigned)
        nodes = [0]

        def forward_check() -> bool:
            for p in self.others:
                if capacity[p] and sum(1 for c in unassigned if p in domains[c]) < capacity[p]:
                    return False
            return all(any(capacity[p] > 0 for p in domains[c]) for c in unassigned)

        def backtrack() -> bool:
            if not unassigned:
                return True
            nodes[0] += 1
            if nodes[0] > self.node_limit:
                return False
            # MRV: the card with the fewest players that can still take it.
            card = min(unassigned, key=lambda c: sum(1 for p in domains[c] if capacity[p] > 0))
            options = [p for p in domains[card] if capacity[p] > 0]
            self.rng.shuffle(options)
            unassigned.remove(card)
            for p in options:
                hands[p].append(card)
                capacity[p] -= 1
                if forward_check() and backtrack():
                    return True
                capacity[p] += 1
                hands[p].pop()
            unassigned.append(card)
            return False

        if not forward_check() or not backtrack():
            return None
        return hands

    def _fill_by_size_only(self) -> Optional[Dict[int, List[Card]]]:
        pool = list(self.unknown)
        self.rng.shuffle(pool)
        hands = {p: list(self.kb.known[p]) for p in self.others}
        for p in self.others:
            need = self.kb.cards_in_hand(p) - len(hands[p])
            if need < 0:
                return None
            hands[p].extend(pool[:need])
            pool = pool[need:]
        return hands

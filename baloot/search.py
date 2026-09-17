"""Alpha-beta search on one fully known (sampled) deal.

Differences from the original implementation:

* The search can continue past the end of the current trick: the trick winner
  leads the next one, up to a horizon measured in tricks. The original stopped
  as soon as the current trick ended, which made the agent greedy.
* Maximizing vs minimizing is decided by team membership, not by flipping a
  flag every ply. Flipping stops being correct once a trick ends, because the
  winner (from either team) leads next.
* It works on private copies of the hands and table, never on the live game.
* The evaluation includes the last-trick bonus.
* In a closed (مقفل) Hokom game, trump leads are restricted as in the real game.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .cards import Card
from .rules import (LAST_TRICK_BONUS, card_points, is_trump, legal_moves,
                    plain_strength, trick_points, trick_winner, trump_strength)

INF = float("inf")


class TrickSearch:
    def __init__(self, me: int, mode: str, trump: Optional[str], horizon_tricks: int,
                 locked: bool = False):
        self.me = me
        self.mode = mode
        self.trump = trump
        self.locked = locked
        self.horizon = max(1, horizon_tricks)
        self.nodes = 0

    def move_values(self, hands: Dict[int, List[Card]], table: Sequence[Tuple[int, Card]],
                    moves: Sequence[Card]) -> Dict[Card, float]:
        """Exact minimax value (to the horizon) of each candidate move."""
        hands = {p: list(h) for p, h in hands.items()}
        table = list(table)
        to_play = (table[0][0] + len(table)) % 4 if table else self.me
        values = {}
        for move in moves:
            hands[to_play].remove(move)
            table.append((to_play, move))
            values[move] = self._ab(hands, table, (to_play + 1) % 4, self.horizon, -INF, INF)
            table.pop()
            hands[to_play].append(move)
        return values

    def _ab(self, hands, table, to_play, tricks_left, alpha, beta) -> float:
        self.nodes += 1
        if len(table) == 4:
            winner = trick_winner(table, self.mode, self.trump)
            pts = trick_points(table, self.mode, self.trump)
            last = all(len(h) == 0 for h in hands.values())
            if last:
                pts += LAST_TRICK_BONUS
            gain = pts if winner % 2 == self.me % 2 else -pts
            if last or tricks_left <= 1:
                return gain
            return gain + self._ab(hands, [], winner, tricks_left - 1, alpha - gain, beta - gain)

        hand = hands[to_play]
        moves = legal_moves(hand, table, self.mode, self.trump, self.locked)
        if not moves:  # inconsistent sample; should not happen
            return 0.0
        moves.sort(key=self._order_key, reverse=True)

        maximizing = to_play % 2 == self.me % 2
        best = -INF if maximizing else INF
        for move in moves:
            hand.remove(move)
            table.append((to_play, move))
            value = self._ab(hands, table, (to_play + 1) % 4, tricks_left, alpha, beta)
            table.pop()
            hand.append(move)
            if maximizing:
                best = max(best, value)
                alpha = max(alpha, value)
            else:
                best = min(best, value)
                beta = min(beta, value)
            if beta <= alpha:
                break
        return best

    def _order_key(self, card: Card):
        """Try strong, valuable cards first: better cutoffs on average."""
        if is_trump(card, self.mode, self.trump):
            return (2, trump_strength(card))
        return (1 if card_points(card, self.mode, self.trump) >= 10 else 0, plain_strength(card))

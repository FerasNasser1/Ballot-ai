"""Main window: connects the engine, the AI agents and the widgets.

Thread safety
-------------
The engine and the knowledge bases are only touched on the GUI thread.
For an AI move, ``agent.plan_move`` copies everything the search needs into a
``DecisionTask`` which runs in a ``MoveWorker`` thread. The worker never sees
the live game. Every scheduled callback carries a token; starting a new round
or match bumps the token, so late results from old workers are ignored.
"""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Optional

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                             QPushButton, QVBoxLayout, QWidget)

from ..agent import BalootAgent
from ..bidding import BUY_ASHKAL, BUY_HOKOM, BUY_HOKOM_THANI, BUY_SUN, PASS
from ..cards import SUIT_SYMBOLS, Card, sort_hand
from ..engine import TARGET_SCORE, GameEngine, Phase
from ..escalation import CALL_LABELS
from ..rules import team_of, trick_points
from ..scoring import LEVEL_NAMES, NORMAL
from . import theme as T
from .dialogs import DeclarationsDialog, MatchOverDialog, RoundSummaryDialog, contract_text
from .widgets import BidPanel, HandWidget, ScoreSheet, SeatWidget, TableWidget

log = logging.getLogger(__name__)


class MoveWorker(QThread):
    # Named move_ready on purpose: QThread already has a built-in "finished" signal.
    move_ready = pyqtSignal(int, int, object)  # token, player id, Card or None

    def __init__(self, token: int, pid: int, task, parent=None):
        super().__init__(parent)
        self.token, self.pid, self.task = token, pid, task

    def run(self):
        try:
            card = self.task.run()
        except Exception:  # never let a search bug kill the thread silently
            log.exception("AI search failed")
            card = None
        self.move_ready.emit(self.token, self.pid, card)


def bid_label(action: str, trump: Optional[str]) -> str:
    if action == PASS:
        return "Pass  بس"
    if action == BUY_SUN:
        return "Sun  صن"
    if action == BUY_ASHKAL:
        return "Ashkal  أشكل"
    return f"Hokom {SUIT_SYMBOLS[trump]}  حكم"


class MainWindow(QMainWindow):
    AI_BID_DELAY_MS = 750
    AI_MIN_THINK_MS = 700
    TRICK_PAUSE_MS = 1300

    def __init__(self, samples: int = 30, time_budget: float = 1.0, seed: Optional[int] = None):
        super().__init__()
        rng = random.Random(seed)
        self.agents = {p: BalootAgent(p, samples=samples, time_budget=time_budget,
                                      seed=rng.randrange(1 << 30)) for p in (1, 2, 3)}
        self.engine = GameEngine(list(self.agents.values()), rng)
        self.token = 0
        self.workers: set = set()
        self.sheet_rows = []
        self._think_started = time.monotonic()

        self.setWindowTitle("Baloot  بلوت")
        self.setMinimumSize(1180, 800)
        self._build_ui()
        QTimer.singleShot(250, self.start_round)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QWidget(objectName="root")
        outer = QHBoxLayout(root)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(22)

        main = QVBoxLayout()
        main.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("Baloot")
        title.setFont(T.serif_font(30))
        title_ar = QLabel("بلوت")
        title_ar.setFont(T.serif_font(28))
        title_ar.setStyleSheet(f"color:{T.SAFFRON};")
        top.addWidget(title)
        top.addSpacing(10)
        top.addWidget(title_ar)
        top.addStretch(1)
        self.contract = QLabel("", objectName="contract")
        top.addWidget(self.contract)
        main.addLayout(top)

        self.seats = {p: SeatWidget(p) for p in range(4)}
        self.table = TableWidget()
        arena = QGridLayout()
        arena.setSpacing(6)
        arena.addWidget(self.seats[2], 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        arena.addWidget(self.seats[3], 1, 0, alignment=Qt.AlignmentFlag.AlignVCenter)
        arena.addWidget(self.table, 1, 1)
        arena.addWidget(self.seats[1], 1, 2, alignment=Qt.AlignmentFlag.AlignVCenter)
        arena.setColumnStretch(1, 1)
        arena.setRowStretch(1, 1)
        main.addLayout(arena, 1)

        self.status = QLabel("", objectName="status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.status)

        self.bid_panel = BidPanel()
        self.bid_panel.bid_chosen.connect(self.on_human_bid)
        main.addWidget(self.bid_panel)

        bottom = QHBoxLayout()
        bottom.addWidget(self.seats[0], alignment=Qt.AlignmentFlag.AlignBottom)
        self.hand = HandWidget()
        self.hand.card_clicked.connect(self.on_human_card)
        bottom.addWidget(self.hand, 1)
        bottom.addSpacing(190)  # balance the seat widget so the hand is centred
        main.addLayout(bottom)

        side = QVBoxLayout()
        side.setSpacing(14)
        self.sheet = ScoreSheet(TARGET_SCORE)
        side.addWidget(self.sheet, 1)

        deductions_title = QLabel("What your partner has deduced")
        deductions_title.setObjectName("sectionTitle")
        side.addWidget(deductions_title)
        self.deductions = QLabel("Nothing yet.", objectName="deductions")
        self.deductions.setWordWrap(True)
        self.deductions.setFixedWidth(250)
        self.deductions.setMinimumHeight(118)
        self.deductions.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        side.addWidget(self.deductions)

        new_match = QPushButton("New match", objectName="quiet")
        new_match.clicked.connect(self.new_match)
        side.addWidget(new_match)

        outer.addLayout(main, 1)
        outer.addLayout(side)
        self.setCentralWidget(root)

    # ------------------------------------------------------------ refresh

    def refresh(self) -> None:
        e = self.engine
        active = e.current_bidder if e.phase == Phase.BIDDING else (
            e.turn if e.phase == Phase.PLAYING else None)
        for pid, seat in self.seats.items():
            badge = ""
            if e.phase != Phase.BIDDING and e.buyer == pid:
                badge = f"Bought {contract_text(e.mode, e.trump, ashkal=e.ashkal)}"
            elif e.doubler == pid and e.level != NORMAL:
                badge = LEVEL_NAMES[e.level]
            elif pid == e.dealer:
                badge = "Dealer"
            caption = "Thinking…" if active == pid and pid != 0 and e.phase == Phase.PLAYING else ""
            seat.set_info(len(e.hands[pid]), active == pid, badge, caption)

        if e.phase == Phase.BIDDING:
            self.contract.setText(f"Ground card {e.public_card}   Round {e.bid_round} of bidding")
        elif e.mode:
            text = contract_text(e.mode, e.trump, e.level, e.locked, e.ashkal)
            self.contract.setText(f"{text}, bought by {T.SEAT_NAMES[e.buyer]}")

        hand = sort_hand(e.hands[0], e.trump)
        my_turn = e.phase == Phase.PLAYING and e.turn == 0
        self.hand.set_cards(hand, e.legal_moves(0) if my_turn else None, e.trump)
        self._refresh_deductions()

    def _refresh_deductions(self) -> None:
        log_lines = self.agents[2].kb.log[-6:]
        if not log_lines:
            self.deductions.setText("Nothing yet. Deductions appear as players fail to follow suit "
                                    "or show declarations.")
            return
        names = {f"P{p}": T.SEAT_NAMES[p] for p in range(4)}
        pretty = []
        for line in log_lines:
            line = re.sub(r"^R\d: ", "", line)
            line = re.sub(r"P\d", lambda m: names[m.group(0)], line)
            line = line.replace("You is", "You are").replace("You holds", "You hold")
            pretty.append(line)
        self.deductions.setText("\n".join(pretty))

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    # ------------------------------------------------------------ rounds

    def new_match(self) -> None:
        self.token += 1
        self.engine.new_match()
        self.sheet_rows = []
        self.sheet.set_history([], (0, 0))
        self.start_round()

    def start_round(self, token: Optional[int] = None) -> None:
        if token is not None and token != self.token:
            return
        self.token += 1
        self.engine.start_round()
        self.table.clear_cards()
        self.table.clear_bubbles()
        self.table.show_public(self.engine.public_card)
        self.refresh()
        self.next_bid()

    # ----------------------------------------------------------- bidding

    def next_bid(self) -> None:
        e = self.engine
        if e.phase != Phase.BIDDING:
            return
        pid = e.current_bidder
        self.refresh()
        if pid == 0:
            self.set_status(self.bid_prompt())
            self.bid_panel.show_options(e.bid_options(), e.bid_round, e.public_card.suit,
                                        e.thani_suits())
        else:
            self.bid_panel.hide_options()
            self.set_status(f"{T.SEAT_NAMES[pid]} is deciding…")
            token = self.token
            QTimer.singleShot(self.AI_BID_DELAY_MS, lambda: self.ai_bid(token, pid))

    def bid_prompt(self) -> str:
        e = self.engine
        if e.hokom_bid is not None:
            who = T.SEAT_NAMES[e.hokom_bid[0]]
            return f"{who} bought Hokom {SUIT_SYMBOLS[e.hokom_bid[1]]}. Take it with Sun, or pass."
        if BUY_ASHKAL in e.bid_options():
            return "Your bid. Sun, Ashkal (the ground card goes to your partner), Hokom, or pass."
        return "Your bid. Buy Sun, buy Hokom, or pass."

    def ai_bid(self, token: int, pid: int) -> None:
        e = self.engine
        if token != self.token or e.phase != Phase.BIDDING or e.current_bidder != pid:
            return
        action, trump = self.agents[pid].choose_bid(e.hands[pid], e.public_card, e.bid_round,
                                                    e.bid_options())
        self.apply_bid(pid, action, trump)

    def on_human_bid(self, action: str, trump) -> None:
        e = self.engine
        if e.phase == Phase.BIDDING and e.current_bidder == 0:
            self.bid_panel.hide_options()
            self.apply_bid(0, action, trump)
        elif e.phase == Phase.DOUBLING and e.escalation_turn == 0:
            self.bid_panel.hide_options()
            self.apply_escalation(0, action)

    def apply_bid(self, pid: int, action: str, trump: Optional[str]) -> None:
        e = self.engine
        outcome = e.apply_bid(pid, action, trump)
        bubble_trump = trump if action in (BUY_HOKOM, BUY_HOKOM_THANI) else None
        self.table.set_bubble(pid, bid_label(action, bubble_trump))
        token = self.token

        if outcome == "redeal":
            self.set_status("Everyone passed twice. Dealing again.")
            self.refresh()
            QTimer.singleShot(1600, lambda: self.start_round(token))
        elif outcome == "second_round":
            self.set_status("Nobody bought. Second round of bidding.")
            self.refresh()
            QTimer.singleShot(1000, lambda: self._second_round(token))
        elif outcome in ("pass", "hokom"):
            if outcome == "hokom":
                self.set_status(f"{T.SEAT_NAMES[pid]} bought Hokom. The others may still take Sun.")
                self.refresh()
                QTimer.singleShot(900, self.next_bid)
                return
            self.next_bid()
        else:
            self.bid_panel.hide_options()
            bought = contract_text(e.mode, e.trump, ashkal=e.ashkal)
            extra = f", {T.SEAT_NAMES[e.taker]} takes the ground card" if e.ashkal else ""
            self.set_status(f"{T.SEAT_NAMES[e.buyer]} bought {bought}{extra}.")
            self.refresh()
            QTimer.singleShot(1300, lambda: self.begin_doubling(token))

    def _second_round(self, token: int) -> None:
        if token != self.token:
            return
        self.table.clear_bubbles()
        self.next_bid()

    # ---------------------------------------------------------- doubling

    def begin_doubling(self, token: int) -> None:
        if token != self.token:
            return
        self.table.clear_bubbles()
        if self.engine.phase == Phase.DOUBLING:
            self.next_escalation()
        else:
            self.begin_play(token)

    def next_escalation(self) -> None:
        e = self.engine
        if e.phase != Phase.DOUBLING:
            self.begin_play(self.token)
            return
        pid = e.escalation_turn
        self.refresh()
        if pid == 0:
            self.set_status("Double the stake? Closed play means nobody may lead a trump."
                            if e.level == NORMAL else "Raise it further?")
            self.bid_panel.show_escalation(e.escalation_options())
        else:
            self.bid_panel.hide_options()
            self.set_status(f"{T.SEAT_NAMES[pid]} is thinking about doubling…")
            token = self.token
            QTimer.singleShot(self.AI_BID_DELAY_MS, lambda: self.ai_escalation(token, pid))

    def ai_escalation(self, token: int, pid: int) -> None:
        e = self.engine
        if token != self.token or e.phase != Phase.DOUBLING or e.escalation_turn != pid:
            return
        self.apply_escalation(pid, self.agents[pid].choose_escalation(e.escalation_view(pid)))

    def apply_escalation(self, pid: int, action: str) -> None:
        e = self.engine
        outcome = e.apply_escalation(pid, action)
        self.table.set_bubble(pid, CALL_LABELS[action])
        token = self.token
        self.refresh()
        if outcome == "done":
            QTimer.singleShot(1200, lambda: self.begin_play(token))
        else:
            QTimer.singleShot(900, self.next_escalation)

    def begin_play(self, token: int) -> None:
        if token != self.token or self.engine.phase != Phase.PLAYING:
            return
        self.table.clear_bubbles()
        self.table.hide_public()
        if self.engine.locked:
            self.set_status("Closed game: nobody may lead a trump.")
        self.next_turn()

    # -------------------------------------------------------------- play

    def next_turn(self) -> None:
        e = self.engine
        if e.phase != Phase.PLAYING:
            return
        pid = e.turn
        self.refresh()
        if pid == 0:
            self.set_status("Your turn. Playable cards are raised when you point at them.")
            return
        self.set_status(f"{T.SEAT_NAMES[pid]} is thinking…")
        task = self.agents[pid].plan_move(e.view_for(pid))
        worker = MoveWorker(self.token, pid, task, self)
        worker.move_ready.connect(self.on_move_ready)
        worker.finished.connect(lambda w=worker: self._worker_done(w))
        self._think_started = time.monotonic()
        self.workers.add(worker)
        worker.start()

    def _worker_done(self, worker: MoveWorker) -> None:
        self.workers.discard(worker)
        worker.deleteLater()

    def on_move_ready(self, token: int, pid: int, card: Optional[Card]) -> None:
        if token != self.token:
            return
        elapsed_ms = int((time.monotonic() - self._think_started) * 1000)
        delay = max(0, self.AI_MIN_THINK_MS - elapsed_ms)
        QTimer.singleShot(delay, lambda: self.apply_ai_play(token, pid, card))

    def apply_ai_play(self, token: int, pid: int, card: Optional[Card]) -> None:
        e = self.engine
        if token != self.token or e.phase != Phase.PLAYING or e.turn != pid:
            return
        legal = e.legal_moves(pid)
        if card not in legal:
            log.warning("AI returned %s, not legal; playing %s", card, legal[0])
            card = legal[0]
        e.play(pid, card)
        self.after_play()

    def on_human_card(self, card: Card) -> None:
        e = self.engine
        if e.phase == Phase.PLAYING and e.turn == 0 and card in e.legal_moves(0):
            e.play(0, card)
            self.after_play()

    def after_play(self) -> None:
        e = self.engine
        self.table.show_table(e.table)
        if e.phase == Phase.TRICK_COMPLETE:
            winner = e.current_winner()
            points = trick_points(e.table, e.mode, e.trump)
            if e.tricks_played == 7:
                points += 10
            self.table.highlight_winner(winner)
            who = "You take" if winner == 0 else f"{T.SEAT_NAMES[winner]} takes"
            self.set_status(f"{who} the trick, {points} points.")
            self.refresh()
            token = self.token
            QTimer.singleShot(self.TRICK_PAUSE_MS, lambda: self.finish_trick(token))
        else:
            self.next_turn()

    def finish_trick(self, token: int) -> None:
        e = self.engine
        if token != self.token or e.phase != Phase.TRICK_COMPLETE:
            return
        result = e.resolve_trick()
        self.table.clear_cards()
        self.refresh()

        decl = result.declarations
        if decl is not None and decl.winning_team is not None and decl.shown:
            DeclarationsDialog(self, decl, e.mode).exec()
            self.refresh()

        if result.round_result is None:
            self.next_turn()
            return

        r = result.round_result
        note = ""
        if r.qahwa:
            note = "قهوة"
        elif r.level != NORMAL:
            note = f"×{r.level}"
        elif r.buyer_failed:
            note = "✗"
        self.sheet_rows.append((r.final[0], r.final[1], note))
        self.sheet.set_history(self.sheet_rows, tuple(e.totals))
        match_over = e.phase == Phase.MATCH_OVER
        RoundSummaryDialog(self, r, match_over).exec()
        if token != self.token:
            return
        if not match_over:
            self.start_round()
            return
        choice = MatchOverDialog(self, e.match_winner, e.totals).exec()
        if choice == MatchOverDialog.NEW_MATCH:
            self.new_match()
        else:
            self.close()

    # ------------------------------------------------------------ closing

    def closeEvent(self, event):
        self.token += 1
        for worker in list(self.workers):
            worker.wait(3000)
        super().closeEvent(event)

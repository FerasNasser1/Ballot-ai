"""Dialogs shown between tricks and rounds."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from ..cards import SUIT_SYMBOLS
from ..engine import RoundResult
from ..rules import HOKOM, DeclarationResult
from ..scoring import LEVEL_NAMES, NORMAL, QAHWA
from . import theme as T
from .widgets import CardWidget


def contract_text(mode: Optional[str], trump: Optional[str], level: int = NORMAL,
                  locked: bool = False, ashkal: bool = False) -> str:
    """For example "Hokom ♥ · Double · closed" or "Sun (Ashkal)"."""
    text = f"Hokom {SUIT_SYMBOLS[trump]}" if mode == HOKOM else ("Sun (Ashkal)" if ashkal else "Sun")
    if level != NORMAL:
        text += f" · {LEVEL_NAMES[level]}"
    if locked:
        text += " · closed"
    return text


def _title(text: str, arabic: str = "") -> QLabel:
    label = QLabel(f"<span style='font-size:24px; font-weight:600'>{text}</span>"
                   + (f"&nbsp;&nbsp;<span style='font-size:22px; color:{T.SAFFRON}'>{arabic}</span>"
                      if arabic else ""))
    return label


class _BaseDialog(QDialog):
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(28, 24, 28, 24)
        self.body.setSpacing(14)

    def add_buttons(self, *buttons: QPushButton) -> None:
        row = QHBoxLayout()
        row.addStretch(1)
        for b in buttons:
            row.addWidget(b)
        self.body.addLayout(row)
        if buttons:
            buttons[-1].setDefault(True)
            buttons[-1].setFocus()


class DeclarationsDialog(_BaseDialog):
    def __init__(self, parent, declarations: DeclarationResult, mode: str):
        super().__init__(parent, "Declarations")
        team = declarations.winning_team
        who = "Your team" if team == 0 else "The other team"
        self.body.addWidget(_title("Declarations", "مشاريع"))
        note = QLabel(f"{who} holds the best project, so only their projects score "
                      f"({declarations.team_points[team]} points this round).")
        note.setWordWrap(True)
        note.setObjectName("muted")
        self.body.addWidget(note)

        for pid, projects in sorted(declarations.shown.items()):
            name = QLabel(T.SEAT_NAMES[pid])
            name.setStyleSheet(f"font-size:16px; font-weight:600; color:{T.TEAM_COLORS[pid % 2]};")
            self.body.addWidget(name)
            for project in projects:
                row = QHBoxLayout()
                label = QLabel(f"{project.name}  ({project.points(mode)})")
                label.setMinimumWidth(110)
                label.setStyleSheet("font-size:15px;")
                row.addWidget(label)
                for card in project.cards:
                    row.addWidget(CardWidget(card, 46, 68))
                row.addStretch(1)
                self.body.addLayout(row)

        ok = QPushButton("Continue")
        ok.clicked.connect(self.accept)
        self.add_buttons(ok)


class RoundSummaryDialog(_BaseDialog):
    def __init__(self, parent, result: RoundResult, match_over: bool):
        super().__init__(parent, "Round result")
        buyer_name = T.SEAT_NAMES[result.buyer]
        self.body.addWidget(_title("Round result", "النتيجة"))
        subtitle = QLabel(f"{contract_text(result.mode, result.trump, result.level, result.locked, result.ashkal)}"
                          f", bought by {buyer_name}")
        subtitle.setObjectName("muted")
        self.body.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(8)
        for col, (text, color) in enumerate((("Us  لنا", T.SAFFRON), ("Them  لهم", T.NAJDI_BLUE)), start=1):
            head = QLabel(text)
            head.setStyleSheet(f"font-size:16px; font-weight:600; color:{color};")
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(head, 0, col)

        rows = [
            ("Card points", result.card_points),
            ("Converted", result.base),
            ("Projects", result.project_points),
            ("This round", result.final),
            ("Match total", result.totals_after),
        ]
        for r, (label, values) in enumerate(rows, start=1):
            name = QLabel(label)
            strong = label in ("This round", "Match total")
            name.setStyleSheet(f"font-size:15px; {'font-weight:600;' if strong else ''}")
            grid.addWidget(name, r, 0)
            for c, v in enumerate(values, start=1):
                cell = QLabel(str(v))
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setStyleSheet(f"font-size:{20 if strong else 15}px; {'font-weight:600;' if strong else ''}")
                grid.addWidget(cell, r, c)
        self.body.addLayout(grid)

        winners = "Your team" if result.winner == 0 else "The other team"
        message = ""
        if result.qahwa:
            message = f"Qahwa! {winners} won the hand, and with it the whole match."
        elif result.level != NORMAL:
            message = (f"{LEVEL_NAMES[result.level]} hand. {winners} won it and "
                       f"takes all {sum(result.final)} points.")
        elif result.buyer_failed:
            message = (f"{buyer_name}'s team did not win the hand, so all "
                       f"{sum(result.final)} points go to the other team.")
        if message:
            banner = QLabel(message)
            banner.setWordWrap(True)
            banner.setStyleSheet(f"color:{T.PAPER}; background:{T.SADU_RED}; border-radius:8px; padding:8px 12px;")
            self.body.addWidget(banner)

        ok = QPushButton("See final result" if match_over else "Deal next round")
        ok.setObjectName("buy")
        ok.clicked.connect(self.accept)
        self.add_buttons(ok)


class MatchOverDialog(_BaseDialog):
    NEW_MATCH = 1
    QUIT = 2

    def __init__(self, parent, winner_team: int, totals):
        super().__init__(parent, "Match over")
        won = winner_team == 0
        self.body.addWidget(_title("Your team wins" if won else "The other team wins",
                                   "مبروك" if won else "حظ أوفر"))
        score = QLabel(f"Final score: us {totals[0]}, them {totals[1]}")
        score.setStyleSheet("font-size:16px;")
        self.body.addWidget(score)
        quit_btn = QPushButton("Close game")
        quit_btn.setObjectName("quiet")
        quit_btn.clicked.connect(lambda: self.done(self.QUIT))
        again = QPushButton("Start a new match")
        again.setObjectName("buy")
        again.clicked.connect(lambda: self.done(self.NEW_MATCH))
        self.add_buttons(quit_btn, again)

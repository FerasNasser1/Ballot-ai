"""Custom-painted widgets. Everything is drawn with QPainter, so the game needs
no image assets and scales cleanly on high-DPI screens."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QWidget

from ..cards import SUIT_SYMBOLS, Card
from . import theme as T

ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
ALIGN_TOP_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop


# ---------------------------------------------------------------------------
# Painting helpers
# ---------------------------------------------------------------------------

def paint_sadu_band(p: QPainter, x: float, y: float, length: float, height: float) -> None:
    """A horizontal strip of Al Sadu weaving: black edges, cream threads and a
    row of alternating cream and black triangles on red."""
    p.save()
    p.translate(x, y)
    p.setClipRect(QRectF(0, 0, length, height))
    p.setPen(Qt.PenStyle.NoPen)
    p.fillRect(QRectF(0, 0, length, height), T.qc(T.SADU_BLACK))

    thread = max(1.5, height * 0.07)
    p.fillRect(QRectF(0, height * 0.12, length, thread), T.qc(T.PAPER))
    p.fillRect(QRectF(0, height * 0.88 - thread, length, thread), T.qc(T.PAPER))

    top, bottom = height * 0.12 + thread * 2, height * 0.88 - thread * 2
    p.fillRect(QRectF(0, top, length, bottom - top), T.qc(T.SADU_RED))

    tri_h = bottom - top
    tri_w = tri_h * 1.3
    count = int(length // tri_w) + 2
    for i in range(count):
        x0 = i * tri_w - tri_w / 2
        if i % 2 == 0:
            poly = QPolygonF([QPointF(x0, bottom), QPointF(x0 + tri_w / 2, top), QPointF(x0 + tri_w, bottom)])
            p.setBrush(T.qc(T.PAPER))
        else:
            poly = QPolygonF([QPointF(x0, top), QPointF(x0 + tri_w / 2, bottom), QPointF(x0 + tri_w, top)])
            p.setBrush(T.qc(T.SADU_BLACK))
        p.drawPolygon(poly)
    p.restore()


def paint_card_face(p: QPainter, r: QRectF, card: Card, trump_marker: bool = False) -> None:
    radius = r.width() * 0.09
    p.setPen(QPen(T.qc(T.PAPER_EDGE), 1))
    p.setBrush(T.qc(T.PAPER))
    p.drawRoundedRect(r, radius, radius)

    ink = T.qc(T.CARD_RED if card.is_red else T.INK)
    w, h = r.width(), r.height()

    def corner():
        p.setPen(ink)
        p.setFont(T.serif_font(max(9, int(w * 0.23))))
        p.drawText(QRectF(-w / 2 + w * 0.07, -h / 2 + h * 0.03, w * 0.4, h * 0.2), ALIGN_TOP_LEFT, card.rank)
        p.setFont(T.ui_font(max(8, int(w * 0.19))))
        p.drawText(QRectF(-w / 2 + w * 0.07, -h / 2 + h * 0.2, w * 0.4, h * 0.2), ALIGN_TOP_LEFT, card.symbol)

    p.save()
    p.translate(r.center())
    corner()
    p.rotate(180)
    corner()
    p.restore()

    center = QRectF(r.x() + w * 0.2, r.y() + h * 0.24, w * 0.6, h * 0.52)
    if card.rank in ("J", "Q", "K"):
        p.setPen(QPen(T.qc(T.SAFFRON), 1.4))
        p.setBrush(T.qc(T.SAFFRON, 28))
        p.drawRoundedRect(center, 4, 4)
        p.setPen(ink)
        p.setFont(T.serif_font(int(w * 0.36)))
        p.drawText(center.adjusted(0, -h * 0.07, 0, -h * 0.07), ALIGN_CENTER, card.rank)
        p.setFont(T.ui_font(int(w * 0.2)))
        p.drawText(center.adjusted(0, h * 0.17, 0, 0), ALIGN_CENTER, card.symbol)
    else:
        p.setPen(ink)
        p.setFont(T.ui_font(int(w * 0.5)))
        p.drawText(center, ALIGN_CENTER, card.symbol)

    if trump_marker:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(T.qc(T.SAFFRON))
        d = max(6.0, w * 0.1)
        p.drawEllipse(QRectF(r.right() - d - w * 0.08, r.top() + h * 0.05, d, d))


def paint_card_back(p: QPainter, r: QRectF) -> None:
    radius = r.width() * 0.09
    p.setPen(QPen(T.qc(T.SADU_BLACK), 1))
    p.setBrush(T.qc(T.SADU_RED))
    p.drawRoundedRect(r, radius, radius)

    inner = r.adjusted(r.width() * 0.09, r.width() * 0.09, -r.width() * 0.09, -r.width() * 0.09)
    path = QPainterPath()
    path.addRoundedRect(inner, radius * 0.6, radius * 0.6)
    p.save()
    p.setClipPath(path)
    p.fillRect(inner, T.qc(T.SADU_RED_DEEP))
    step = max(6.0, inner.width() / 4)
    p.setPen(Qt.PenStyle.NoPen)
    row = 0
    y = inner.top()
    while y < inner.bottom() + step:
        x = inner.left() + (step / 2 if row % 2 else 0)
        while x < inner.right() + step:
            diamond = QPolygonF([QPointF(x, y - step * 0.4), QPointF(x + step * 0.4, y),
                                 QPointF(x, y + step * 0.4), QPointF(x - step * 0.4, y)])
            p.setBrush(T.qc(T.PAPER if (row + int(x / step)) % 3 == 0 else T.SADU_BLACK, 210))
            p.drawPolygon(diamond)
            x += step
        y += step * 0.8
        row += 1
    p.restore()
    p.setPen(QPen(T.qc(T.PAPER, 200), 1.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(inner, radius * 0.6, radius * 0.6)


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

class CardWidget(QWidget):
    clicked = pyqtSignal(object)

    LIFT = 14

    def __init__(self, card: Optional[Card], width: int = 84, height: int = 122,
                 interactive: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.card = card
        self.card_w, self.card_h = width, height
        self.interactive = interactive
        self.lift = self.LIFT if interactive else 0
        self.face_up = card is not None
        self.playable = False
        self.dimmed = False
        self.hovered = False
        self.highlight = False
        self.trump_marker = False
        self.setFixedSize(width + 6, height + self.lift + 6)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_state(self, playable: bool = False, dimmed: bool = False, trump_marker: bool = False) -> None:
        self.playable, self.dimmed, self.trump_marker = playable, dimmed, trump_marker
        if not playable:
            self.hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor if playable else Qt.CursorShape.ArrowCursor)
        self.setToolTip(f"{self.card} cannot be played now" if dimmed and self.card else "")
        self.update()

    def set_highlight(self, on: bool) -> None:
        self.highlight = on
        self.update()

    def enterEvent(self, event):
        if self.interactive and self.playable:
            self.hovered = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.hovered:
            self.hovered = False
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.playable and self.card is not None:
            self.clicked.emit(self.card)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = 3 if self.hovered else 3 + self.lift
        r = QRectF(3, y, self.card_w, self.card_h)
        radius = r.width() * 0.09

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90 if self.hovered else 60))
        p.drawRoundedRect(r.translated(0, 3), radius, radius)

        if self.face_up and self.card is not None:
            paint_card_face(p, r, self.card, self.trump_marker)
        else:
            paint_card_back(p, r)

        if self.dimmed:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(T.qc(T.COFFEE_900, 140))
            p.drawRoundedRect(r, radius, radius)
        if self.highlight:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(T.qc(T.SAFFRON), 3))
            p.drawRoundedRect(r.adjusted(-1, -1, 1, 1), radius, radius)
        p.end()


# ---------------------------------------------------------------------------
# Table (the Sadu rug)
# ---------------------------------------------------------------------------

class TableWidget(QWidget):
    CARD_W, CARD_H = 74, 108

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(520, 380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.slot_cards: Dict[int, CardWidget] = {}
        self.bubbles: Dict[int, str] = {}
        self.public: Optional[CardWidget] = None

    # -- content --------------------------------------------------------------

    def show_public(self, card: Card) -> None:
        self.hide_public()
        self.public = CardWidget(card, self.CARD_W, self.CARD_H, parent=self)
        self.public.show()
        self._place()

    def hide_public(self) -> None:
        if self.public:
            self.public.deleteLater()
            self.public = None

    def set_bubble(self, pid: int, text: str) -> None:
        self.bubbles[pid] = text
        self.update()

    def clear_bubbles(self) -> None:
        self.bubbles.clear()
        self.update()

    def show_table(self, table: Sequence[Tuple[int, Card]]) -> None:
        on_table = dict(table)
        for pid in list(self.slot_cards):
            if pid not in on_table:
                self.slot_cards.pop(pid).deleteLater()
        for pid, card in on_table.items():
            if pid not in self.slot_cards:
                widget = CardWidget(card, self.CARD_W, self.CARD_H, parent=self)
                widget.show()
                self.slot_cards[pid] = widget
        self._place()

    def highlight_winner(self, pid: Optional[int]) -> None:
        for seat, widget in self.slot_cards.items():
            widget.set_highlight(seat == pid)

    def clear_cards(self) -> None:
        for widget in self.slot_cards.values():
            widget.deleteLater()
        self.slot_cards.clear()

    # -- geometry -------------------------------------------------------------

    def _rug(self) -> QRectF:
        return QRectF(self.rect()).adjusted(6, 6, -6, -6)

    def _slot_center(self, pid: int) -> QPointF:
        rug = self._rug()
        c = rug.center()
        dx, dy = rug.width() * 0.25, rug.height() * 0.27
        return {0: QPointF(c.x(), c.y() + dy), 1: QPointF(c.x() + dx, c.y()),
                2: QPointF(c.x(), c.y() - dy), 3: QPointF(c.x() - dx, c.y())}[pid]

    def _place(self) -> None:
        for pid, widget in self.slot_cards.items():
            center = self._slot_center(pid)
            widget.move(int(center.x() - widget.width() / 2), int(center.y() - widget.height() / 2))
            widget.raise_()
        if self.public:
            c = self._rug().center()
            self.public.move(int(c.x() - self.public.width() / 2), int(c.y() - self.public.height() / 2))

    def resizeEvent(self, event):
        self._place()
        super().resizeEvent(event)

    # -- painting -------------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rug = self._rug()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRect(rug.translated(0, 5))
        p.fillRect(rug, T.qc(T.SADU_RED_DEEP))

        # Faint woven lattice in the field
        p.save()
        p.setClipRect(rug)
        p.setPen(QPen(T.qc(T.SADU_BLACK, 55), 1))
        step = 34
        x = rug.left() - rug.height()
        while x < rug.right():
            p.drawLine(QPointF(x, rug.top()), QPointF(x + rug.height(), rug.bottom()))
            p.drawLine(QPointF(x + rug.height(), rug.top()), QPointF(x, rug.bottom()))
            x += step
        p.restore()

        band = 26.0
        paint_sadu_band(p, rug.left(), rug.top(), rug.width(), band)
        p.save()
        p.translate(rug.right(), rug.bottom())
        p.rotate(180)
        paint_sadu_band(p, 0, 0, rug.width(), band)
        p.restore()
        p.save()
        p.translate(rug.left(), rug.bottom())
        p.rotate(-90)
        paint_sadu_band(p, 0, 0, rug.height(), band)
        p.restore()
        p.save()
        p.translate(rug.right(), rug.top())
        p.rotate(90)
        paint_sadu_band(p, 0, 0, rug.height(), band)
        p.restore()
        for cx, cy in ((rug.left(), rug.top()), (rug.right() - band, rug.top()),
                       (rug.left(), rug.bottom() - band), (rug.right() - band, rug.bottom() - band)):
            square = QRectF(cx, cy, band, band)
            p.fillRect(square, T.qc(T.SADU_BLACK))
            c = square.center()
            p.setBrush(T.qc(T.PAPER))
            p.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - 7), QPointF(c.x() + 7, c.y()),
                                     QPointF(c.x(), c.y() + 7), QPointF(c.x() - 7, c.y())]))

        # Central medallion
        c = rug.center()
        m = min(rug.width(), rug.height()) * 0.2
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(T.qc(T.PAPER, 45), 2))
        p.drawPolygon(QPolygonF([QPointF(c.x(), c.y() - m), QPointF(c.x() + m * 1.3, c.y()),
                                 QPointF(c.x(), c.y() + m), QPointF(c.x() - m * 1.3, c.y())]))

        # Empty slots and bid bubbles
        for pid in range(4):
            center = self._slot_center(pid)
            slot = QRectF(center.x() - self.CARD_W / 2, center.y() - self.CARD_H / 2, self.CARD_W, self.CARD_H)
            if pid not in self.slot_cards and pid not in self.bubbles:
                pen = QPen(T.qc(T.PAPER, 60), 1.5, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(slot, 7, 7)
            if pid in self.bubbles:
                text = self.bubbles[pid]
                font = T.ui_font(15, QFont.Weight.DemiBold)
                p.setFont(font)
                width = max(84, p.fontMetrics().horizontalAdvance(text) + 32)
                pill = QRectF(center.x() - width / 2, center.y() - 19, width, 38)
                bought = not text.startswith(("Pass", "No "))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(T.qc(T.SAFFRON if bought else T.PAPER))
                p.drawRoundedRect(pill, 19, 19)
                p.setPen(T.qc(T.SADU_BLACK if bought else T.INK))
                p.drawText(pill, ALIGN_CENTER, text)
        p.end()


# ---------------------------------------------------------------------------
# Seat
# ---------------------------------------------------------------------------

class SeatWidget(QWidget):
    def __init__(self, pid: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.pid = pid
        self.active = False
        self.card_count = 0
        self.badge = ""
        self.caption = ""
        self.setFixedSize(190, 96)

    def set_info(self, card_count: int, active: bool, badge: str = "", caption: str = "") -> None:
        self.card_count, self.active, self.badge, self.caption = card_count, active, badge, caption
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        team_color = T.qc(T.TEAM_COLORS[self.pid % 2])

        avatar = QRectF(8, 14, 56, 56)
        if self.active:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(T.qc(T.SAFFRON, 70))
            p.drawEllipse(avatar.adjusted(-7, -7, 7, 7))
        p.setPen(QPen(team_color, 3))
        p.setBrush(T.qc(T.COFFEE_700))
        p.drawEllipse(avatar)
        p.setPen(T.qc(T.PAPER))
        p.setFont(T.ui_font(20, QFont.Weight.DemiBold))
        p.drawText(avatar, ALIGN_CENTER, {0: "أ", 1: "ي", 2: "ش", 3: "س"}[self.pid])

        p.setPen(T.qc(T.PAPER))
        p.setFont(T.ui_font(16, QFont.Weight.DemiBold))
        p.drawText(QRectF(74, 8, 116, 22), ALIGN_TOP_LEFT, T.SEAT_NAMES[self.pid])
        p.setPen(T.qc(T.COFFEE_400))
        p.setFont(T.ui_font(13))
        p.drawText(QRectF(74, 30, 116, 20), ALIGN_TOP_LEFT, self.caption or T.SEAT_NAMES_AR[self.pid])

        if self.badge:
            p.setFont(T.ui_font(12, QFont.Weight.DemiBold))
            w = p.fontMetrics().horizontalAdvance(self.badge) + 16
            pill = QRectF(74, 52, w, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(team_color)
            p.drawRoundedRect(pill, 10, 10)
            p.setPen(T.qc(T.SADU_BLACK))
            p.drawText(pill, ALIGN_CENTER, self.badge)

        if self.pid != 0 and self.card_count:
            for i in range(self.card_count):
                paint_card_back(p, QRectF(74 + i * 9, 76, 14, 18))
        p.end()


# ---------------------------------------------------------------------------
# Human hand
# ---------------------------------------------------------------------------

class HandWidget(QWidget):
    card_clicked = pyqtSignal(object)

    CARD_W, CARD_H = 88, 128

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.widgets: List[CardWidget] = []
        self.setMinimumHeight(self.CARD_H + CardWidget.LIFT + 10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_cards(self, cards: Sequence[Card], playable: Optional[Iterable[Card]],
                  trump: Optional[str]) -> None:
        """``playable=None`` shows the hand without interaction (not our turn)."""
        playable_set = set(playable) if playable is not None else None
        current = [w.card for w in self.widgets]
        if current != list(cards):
            for w in self.widgets:
                w.deleteLater()
            self.widgets = []
            for card in cards:
                widget = CardWidget(card, self.CARD_W, self.CARD_H, interactive=True, parent=self)
                widget.clicked.connect(self.card_clicked.emit)
                widget.show()
                self.widgets.append(widget)
        for w in self.widgets:
            is_trump = trump is not None and w.card.suit == trump
            if playable_set is None:
                w.set_state(playable=False, dimmed=False, trump_marker=is_trump)
            else:
                legal = w.card in playable_set
                w.set_state(playable=legal, dimmed=not legal, trump_marker=is_trump)
        self._place()

    def _place(self) -> None:
        n = len(self.widgets)
        if not n:
            return
        w = self.widgets[0].width()
        step = w + 10 if n == 1 else min(w + 10, (self.width() - w) / (n - 1))
        total = step * (n - 1) + w
        x0 = (self.width() - total) / 2
        for i, widget in enumerate(self.widgets):
            widget.move(int(x0 + i * step), 4)
            widget.raise_()

    def resizeEvent(self, event):
        self._place()
        super().resizeEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(8 * (self.CARD_W + 10), self.CARD_H + CardWidget.LIFT + 10)


# ---------------------------------------------------------------------------
# Score sheet
# ---------------------------------------------------------------------------

class ScoreSheet(QWidget):
    """Paper tally in the style people keep at a real game: لنا on one side,
    لهم on the other, one line per round."""

    def __init__(self, target: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.target = target
        self.rows: List[Tuple[int, int, str]] = []
        self.totals = (0, 0)
        self.setFixedWidth(250)
        self.setMinimumHeight(360)

    def set_history(self, rows: List[Tuple[int, int, str]], totals: Tuple[int, int]) -> None:
        self.rows, self.totals = rows, totals
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sheet = QRectF(self.rect()).adjusted(2, 2, -2, -6)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(sheet.translated(0, 4), 6, 6)
        p.setBrush(T.qc(T.PAPER))
        p.drawRoundedRect(sheet, 6, 6)

        mid = sheet.center().x()
        p.setPen(T.qc(T.INK))
        p.setFont(T.serif_font(24))
        p.drawText(QRectF(sheet.left(), sheet.top() + 12, sheet.width() / 2, 34), ALIGN_CENTER, "لنا")
        p.drawText(QRectF(mid, sheet.top() + 12, sheet.width() / 2, 34), ALIGN_CENTER, "لهم")
        p.setFont(T.ui_font(12))
        p.setPen(T.qc(T.COFFEE_400))
        p.drawText(QRectF(sheet.left(), sheet.top() + 44, sheet.width() / 2, 18), ALIGN_CENTER, "Us")
        p.drawText(QRectF(mid, sheet.top() + 44, sheet.width() / 2, 18), ALIGN_CENTER, "Them")

        for t, x in ((0, sheet.left() + 22), (1, mid + 22)):
            p.setPen(QPen(T.qc(T.TEAM_COLORS[t]), 3))
            p.drawLine(QPointF(x, sheet.top() + 66), QPointF(x + sheet.width() / 2 - 44, sheet.top() + 66))

        p.setPen(QPen(T.qc(T.PAPER_EDGE), 1))
        top = sheet.top() + 76
        bottom = sheet.bottom() - 74
        p.drawLine(QPointF(mid, top), QPointF(mid, bottom))

        line_h = 26
        visible = max(1, int((bottom - top) // line_h))
        rows = self.rows[-visible:]
        p.setFont(T.serif_font(17, QFont.Weight.Normal))
        for i, (us, them, note) in enumerate(rows):
            y = top + i * line_h
            p.setPen(QPen(T.qc(T.PAPER_EDGE, 140), 1))
            p.drawLine(QPointF(sheet.left() + 14, y + line_h), QPointF(sheet.right() - 14, y + line_h))
            p.setPen(T.qc(T.INK))
            p.drawText(QRectF(sheet.left(), y, sheet.width() / 2, line_h), ALIGN_CENTER, str(us))
            p.drawText(QRectF(mid, y, sheet.width() / 2, line_h), ALIGN_CENTER, str(them))
            if note:
                p.setPen(T.qc(T.CARD_RED))
                p.setFont(T.ui_font(11))
                p.drawText(QRectF(sheet.left() + 4, y, 40, line_h), ALIGN_CENTER, note)
                p.setFont(T.serif_font(17, QFont.Weight.Normal))

        p.setPen(QPen(T.qc(T.INK), 1.2))
        p.drawLine(QPointF(sheet.left() + 14, bottom + 4), QPointF(sheet.right() - 14, bottom + 4))
        p.drawLine(QPointF(sheet.left() + 14, bottom + 8), QPointF(sheet.right() - 14, bottom + 8))
        p.setFont(T.serif_font(28))
        p.drawText(QRectF(sheet.left(), bottom + 12, sheet.width() / 2, 36), ALIGN_CENTER, str(self.totals[0]))
        p.drawText(QRectF(mid, bottom + 12, sheet.width() / 2, 36), ALIGN_CENTER, str(self.totals[1]))
        p.setFont(T.ui_font(12))
        p.setPen(T.qc(T.COFFEE_400))
        p.drawText(QRectF(sheet.left(), sheet.bottom() - 24, sheet.width(), 18), ALIGN_CENTER,
                   f"First team to {self.target} wins")
        p.end()


# ---------------------------------------------------------------------------
# Bidding
# ---------------------------------------------------------------------------

class BidPanel(QWidget):
    bid_chosen = pyqtSignal(str, object)  # action, trump suit or None

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(10)
        self.setFixedHeight(48)

    def _clear(self) -> None:
        while self.layout_.count():
            item = self.layout_.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _button(self, text: str, name: str = "", on_click=None) -> QPushButton:
        btn = QPushButton(text)
        if name:
            btn.setObjectName(name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if on_click:
            btn.clicked.connect(on_click)
        self.layout_.addWidget(btn)
        return btn

    def show_options(self, options: Sequence[str], bid_round: int, ground_suit: str,
                     thani_suits: Sequence[str]) -> None:
        """Buttons for the calls the engine allows right now."""
        from ..bidding import BUY_ASHKAL, BUY_HOKOM, BUY_HOKOM_THANI, BUY_SUN, PASS
        self._clear()
        self.layout_.addStretch(1)
        if PASS in options:
            label = "Pass  بس" if bid_round == 1 else "Pass  ولا"
            self._button(label, "quiet", lambda: self.bid_chosen.emit(PASS, None))
        if BUY_SUN in options:
            self._button("Buy Sun  صن", "buy", lambda: self.bid_chosen.emit(BUY_SUN, None))
        if BUY_ASHKAL in options:
            btn = self._button("Ashkal  أشكل", "buy", lambda: self.bid_chosen.emit(BUY_ASHKAL, None))
            btn.setToolTip("Sun, but the ground card goes to your partner")
        if BUY_HOKOM in options:
            self._button(f"Buy Hokom {SUIT_SYMBOLS[ground_suit]}  حكم", "buy",
                         lambda: self.bid_chosen.emit(BUY_HOKOM, ground_suit))
        if BUY_HOKOM_THANI in options:
            self._button("Hokom in another suit  حكم ثاني", "buy",
                         lambda: self._show_suits(options, bid_round, ground_suit, thani_suits))
        self.layout_.addStretch(1)
        self.show()

    def _show_suits(self, options, bid_round, ground_suit, thani_suits) -> None:
        from ..bidding import BUY_HOKOM_THANI
        self._clear()
        self.layout_.addStretch(1)
        self._button("Back", "quiet", lambda: self.show_options(options, bid_round, ground_suit, thani_suits))
        for suit in thani_suits:
            self._button(f"{SUIT_SYMBOLS[suit]}  {suit}", "buy",
                         lambda _=False, s=suit: self.bid_chosen.emit(BUY_HOKOM_THANI, s))
        self.layout_.addStretch(1)

    def show_escalation(self, options: Sequence[str]) -> None:
        """Double / Three / Four / Qahwa buttons. Emits (call, None)."""
        from ..escalation import CALL_LABELS, PASS
        self._clear()
        self.layout_.addStretch(1)
        for option in options:
            name = "quiet" if option == PASS else "buy"
            self._button(CALL_LABELS[option], name,
                         lambda _=False, o=option: self.bid_chosen.emit(o, None))
        self.layout_.addStretch(1)
        self.show()

    def hide_options(self) -> None:
        self._clear()

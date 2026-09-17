"""Visual identity: an evening majlis.

A dark qahwa-brown room, a table drawn as an Al Sadu woven rug, cream cards,
saffron for our team and Najdi-door blue for theirs.
"""

from PyQt6.QtGui import QColor, QFont

COFFEE_900 = "#1B120C"   # window background
COFFEE_800 = "#251912"   # panels, dialogs
COFFEE_700 = "#35251B"   # raised surfaces
COFFEE_400 = "#8A6D57"   # muted text
SADU_RED = "#8E2B24"
SADU_RED_DEEP = "#661B16"
SADU_BLACK = "#1A1411"
PAPER = "#F6EEDC"
PAPER_EDGE = "#CDB892"
INK = "#2A1F18"
CARD_RED = "#A3231B"
SAFFRON = "#D8A93F"
NAJDI_BLUE = "#5B8DB0"

TEAM_COLORS = {0: SAFFRON, 1: NAJDI_BLUE}

SEAT_NAMES = {0: "You", 1: "Right", 2: "Partner", 3: "Left"}
SEAT_NAMES_AR = {0: "أنت", 1: "اليمين", 2: "الشريك", 3: "اليسار"}

UI_FAMILIES = ["Segoe UI", "Noto Sans", "Noto Sans Arabic", "Tahoma", "DejaVu Sans"]
SERIF_FAMILIES = ["Georgia", "Noto Serif", "DejaVu Serif", "Times New Roman"]


def qc(hex_color: str, alpha: int = 255) -> QColor:
    color = QColor(hex_color)
    color.setAlpha(alpha)
    return color


def ui_font(px: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setFamilies(UI_FAMILIES)
    font.setPixelSize(px)
    font.setWeight(weight)
    return font


def serif_font(px: int, weight: QFont.Weight = QFont.Weight.Bold) -> QFont:
    font = QFont()
    font.setFamilies(SERIF_FAMILIES)
    font.setPixelSize(px)
    font.setWeight(weight)
    return font


APP_QSS = f"""
QMainWindow, QWidget#root, QDialog {{
    background: {COFFEE_900};
    color: {PAPER};
}}
QLabel {{ color: {PAPER}; background: transparent; }}
QLabel#muted {{ color: {COFFEE_400}; }}
QLabel#status {{
    color: {PAPER};
    font-size: 17px;
    padding: 6px 0;
}}
QLabel#contract {{
    background: {COFFEE_700};
    border: 1px solid {SADU_RED};
    border-radius: 16px;
    padding: 6px 16px;
    font-size: 15px;
}}
QLabel#sectionTitle {{ font-size: 15px; font-weight: 600; color: {PAPER}; }}
QLabel#deductions {{
    background: {COFFEE_800};
    border-radius: 10px;
    padding: 10px 12px;
    color: {PAPER};
    font-size: 13px;
}}
QPushButton {{
    background: {PAPER};
    color: {INK};
    border: none;
    border-radius: 19px;
    padding: 9px 22px;
    font-size: 15px;
    font-weight: 600;
    min-height: 20px;
}}
QPushButton:hover {{ background: #FFF8E8; }}
QPushButton:pressed {{ background: {PAPER_EDGE}; }}
QPushButton:focus {{ outline: none; border: 2px solid {SAFFRON}; }}
QPushButton:disabled {{ background: {COFFEE_700}; color: {COFFEE_400}; }}
QPushButton#buy {{ background: {SAFFRON}; color: {SADU_BLACK}; }}
QPushButton#buy:hover {{ background: #E6BC5A; }}
QPushButton#quiet {{
    background: transparent;
    color: {PAPER};
    border: 1px solid {COFFEE_400};
}}
QPushButton#quiet:hover {{ border-color: {PAPER}; }}
QDialog {{ border: 2px solid {SADU_RED}; }}
"""


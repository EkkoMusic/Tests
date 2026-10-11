"""Feuille de style Qt générée à partir des jetons du design system."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from .tokens import COLORS as C
from .tokens import FONT as F
from .tokens import RADIUS as R
from .tokens import SPACE as S


def build_stylesheet() -> str:
    return f"""
* {{
    font-family: {F.family};
    font-size: {F.md}px;
    color: {C.text};
    outline: none;
}}
QMainWindow, QDialog, #AppRoot {{ background: {C.bg}; }}
QWidget#Panel, QFrame#Panel {{ background: {C.surface}; border-radius: {R.lg}px; }}
QWidget#TopBar {{ background: {C.surface}; border-bottom: 1px solid {C.border}; }}
QWidget#StatusBar {{ background: {C.surface}; border-top: 1px solid {C.border}; }}
QWidget#Transparent, QScrollArea#Transparent, QScrollArea#Transparent > QWidget > QWidget {{ background: transparent; }}

/* ---------- Texte ---------- */
QLabel {{ background: transparent; }}
QLabel[role="brand"] {{ font-family: {F.display_family}; font-size: {F.lg}px; font-weight: 600; }}
QLabel[role="title"] {{ font-family: {F.display_family}; font-size: {F.xl}px; font-weight: 600; }}
QLabel[role="display"] {{ font-family: {F.display_family}; font-size: {F.xxl}px; font-weight: 600; }}
QLabel[role="section"] {{ color: {C.text_3}; font-size: {F.xs}px; font-weight: 600; }}
QLabel[role="muted"] {{ color: {C.text_2}; }}
QLabel[role="caption"] {{ color: {C.text_3}; font-size: {F.sm}px; }}
QLabel[role="mono"] {{ font-family: {F.mono_family}; color: {C.text_2}; font-size: {F.sm}px; }}
QLabel[role="kbd"] {{
    background: {C.surface_2}; border: 1px solid {C.border_strong}; border-bottom-width: 2px;
    border-radius: {R.sm}px; padding: 3px 8px; font-size: {F.sm}px; font-weight: 600;
}}
QLabel[role="dirty"] {{ color: {C.warning}; font-size: {F.sm}px; }}

/* ---------- Pastilles d'état ---------- */
QLabel[pill] {{ border-radius: 10px; padding: 2px 9px; font-size: {F.xs}px; font-weight: 600; }}
QLabel[pill="success"] {{ background: {C.success_soft}; color: {C.success}; }}
QLabel[pill="error"]   {{ background: {C.error_soft}; color: {C.error}; }}
QLabel[pill="warning"] {{ background: {C.warning_soft}; color: {C.warning}; }}
QLabel[pill="neutral"] {{ background: {C.surface_2}; color: {C.text_2}; }}
QLabel[pill="accent"]  {{ background: {C.accent_soft}; color: {C.accent_hover}; }}

/* ---------- Boutons ---------- */
QPushButton {{
    background: {C.surface_2}; border: 1px solid {C.border_strong}; border-radius: {R.md}px;
    padding: 7px 14px; font-weight: 500; min-height: 18px;
}}
QPushButton:hover {{ background: {C.surface_3}; }}
QPushButton:pressed {{ background: {C.border}; }}
QPushButton:disabled {{ color: {C.text_3}; background: {C.surface}; border-color: {C.border}; }}
QPushButton:focus {{ border-color: {C.accent}; }}
QPushButton[variant="ghost"] {{ background: transparent; border-color: transparent; color: {C.text_2}; }}
QPushButton[variant="ghost"]:hover {{ background: {C.surface_2}; color: {C.text}; }}
QPushButton[variant="ghost"]:focus {{ border-color: {C.accent}; }}
QPushButton[variant="primary"] {{ background: {C.accent}; border-color: {C.accent}; color: {C.on_accent}; font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background: {C.accent_hover}; border-color: {C.accent_hover}; }}
QPushButton[variant="primary"]:pressed {{ background: {C.accent_pressed}; }}
QPushButton[variant="primary"]:disabled {{ background: {C.surface_2}; border-color: {C.border}; color: {C.text_3}; }}
QPushButton[variant="danger"] {{ background: {C.error}; border-color: {C.error}; color: {C.on_accent}; font-weight: 600; }}
QPushButton[variant="danger"]:hover {{ background: #F47E83; }}
QPushButton[variant="launch"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C.accent}, stop:1 {C.accent_2});
    border: none; border-radius: {R.md}px; color: {C.on_accent};
    font-family: {F.display_family}; font-size: {F.md}px; font-weight: 700; padding: 9px 20px;
}}
QPushButton[variant="launch"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {C.accent_hover}, stop:1 #B394FF);
}}
QPushButton[variant="launch"]:pressed {{ background: {C.accent_pressed}; }}
QPushButton[variant="launch"]:disabled {{ background: {C.surface_2}; color: {C.text_3}; }}
QPushButton[variant="segment"] {{
    background: transparent; border: none; border-radius: {R.sm}px; padding: 6px 10px; color: {C.text_2};
}}
QPushButton[variant="segment"]:hover {{ color: {C.text}; }}
QPushButton[variant="segment"]:checked {{ background: {C.surface_3}; color: {C.text}; font-weight: 600; }}
QFrame#Segmented {{ background: {C.bg}; border: 1px solid {C.border}; border-radius: {R.md}px; }}

QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: {R.md}px; padding: 6px; }}
QToolButton:hover {{ background: {C.surface_2}; }}
QToolButton:pressed {{ background: {C.surface_3}; }}
QToolButton:focus {{ border-color: {C.accent}; }}
QToolButton[variant="round"] {{ background: {C.accent}; border-radius: 18px; }}
QToolButton[variant="round"]:hover {{ background: {C.accent_hover}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

/* ---------- Champs ---------- */
QLineEdit, QSpinBox, QComboBox {{
    background: {C.bg}; border: 1px solid {C.border_strong}; border-radius: {R.md}px;
    padding: 7px 10px; selection-background-color: {C.accent}; selection-color: {C.on_accent};
}}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{ border-color: #46526A; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {C.accent}; }}
QLineEdit:read-only {{ color: {C.text_2}; background: {C.surface}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {C.text_3}; border-color: {C.border}; }}
QLineEdit[role="title-edit"] {{ background: transparent; border-color: transparent; font-size: {F.lg}px; font-weight: 600; padding: 4px 6px; }}
QLineEdit[role="title-edit"]:hover {{ border-color: {C.border_strong}; }}
QLineEdit[role="title-edit"]:focus {{ border-color: {C.accent}; background: {C.bg}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {C.surface_2}; border: 1px solid {C.border_strong}; border-radius: {R.md}px; padding: 4px;
    selection-background-color: {C.accent_soft}; selection-color: {C.text};
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{ width: 34px; height: 20px; border-radius: 10px; background: {C.surface_3}; border: 1px solid {C.border_strong}; }}
QCheckBox::indicator:checked {{ background: {C.accent}; border-color: {C.accent}; }}
QCheckBox::indicator:disabled {{ background: {C.surface_2}; }}
QRadioButton {{ spacing: 8px; background: transparent; }}

/* ---------- Curseurs ---------- */
QSlider::groove:horizontal {{ height: 4px; background: {C.surface_3}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {C.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; background: {C.text}; }}
QSlider::handle:horizontal:hover {{ background: #FFFFFF; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QSlider::sub-page:horizontal:disabled {{ background: {C.text_3}; }}

/* ---------- Listes, défilement ---------- */
QListView, QListWidget {{ background: transparent; border: none; }}
QListWidget#NavList::item {{ padding: 9px 12px; border-radius: {R.md}px; color: {C.text_2}; margin: 1px 0; }}
QListWidget#NavList::item:hover {{ background: {C.surface_2}; color: {C.text}; }}
QListWidget#NavList::item:selected {{ background: {C.accent_soft}; color: {C.text}; }}
QListWidget#IssueList::item {{ padding: 6px 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {C.surface_3}; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {C.border_strong}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {C.surface_3}; border-radius: 3px; min-width: 32px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: {S.sm}px; }}
QSplitter::handle:vertical {{ height: {S.sm}px; }}

/* ---------- Menus, infobulles ---------- */
QMenu {{ background: {C.surface_2}; border: 1px solid {C.border_strong}; border-radius: {R.md}px; padding: 6px; }}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: {R.sm}px; }}
QMenu::item:selected {{ background: {C.accent_soft}; }}
QMenu::item:disabled {{ color: {C.text_3}; }}
QMenu::separator {{ height: 1px; background: {C.border_strong}; margin: 5px 6px; }}
QMenu::icon {{ padding-left: 8px; }}
QToolTip {{ background: {C.surface_3}; color: {C.text}; border: 1px solid {C.border_strong}; border-radius: {R.sm}px; padding: 5px 8px; }}

QFrame#Divider {{ background: {C.border}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#VDivider {{ background: {C.border}; max-width: 1px; min-width: 1px; border: none; }}
QFrame#Card {{ background: {C.surface_2}; border-radius: {R.lg}px; }}
QFrame#Toast {{ background: {C.surface_3}; border: 1px solid {C.border_strong}; border-radius: {R.lg}px; }}
QFrame#ThumbFrame {{ background: {C.black}; border: 1px solid {C.border}; border-radius: {R.md}px; }}
QFrame#DropZone {{ border: 1.5px dashed {C.border_strong}; border-radius: {R.lg}px; background: transparent; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: C.bg,
        QPalette.ColorRole.WindowText: C.text,
        QPalette.ColorRole.Base: C.bg,
        QPalette.ColorRole.AlternateBase: C.surface,
        QPalette.ColorRole.Text: C.text,
        QPalette.ColorRole.Button: C.surface_2,
        QPalette.ColorRole.ButtonText: C.text,
        QPalette.ColorRole.Highlight: C.accent,
        QPalette.ColorRole.HighlightedText: C.on_accent,
        QPalette.ColorRole.ToolTipBase: C.surface_3,
        QPalette.ColorRole.ToolTipText: C.text,
        QPalette.ColorRole.PlaceholderText: C.text_3,
        QPalette.ColorRole.Link: C.accent,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(C.text_3))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(C.text_3))
    app.setPalette(palette)
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"])
    font.setPixelSize(F.md)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)
    app.setStyleSheet(build_stylesheet())

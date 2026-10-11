"""Boîtes de dialogue du mode préparation, harmonisées avec le design system.

Elles ne sont jamais ouvertes pendant le mode spectacle.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.media.media_validator import Issue, Severity
from app.persistence.autosave import RecoveryEntry

from .theme import icons
from .theme.tokens import COLORS, SPACE
from .widgets.common import button, label


class StyledDialog(QDialog):
    """En-tête icône + titre + message, contenu libre, rangée de boutons."""

    def __init__(self, parent: QWidget | None, title: str, message: str = "", icon_name: str = "info",
                 icon_color: str = COLORS.accent, width: int = 460) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.result_key: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.lg)
        root.setSpacing(SPACE.md)
        head = QHBoxLayout()
        head.setSpacing(SPACE.md)
        badge = QLabel()
        badge.setPixmap(icons.pixmap(icon_name, icon_color, 26))
        badge.setAlignment(Qt.AlignmentFlag.AlignTop)
        head.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(SPACE.xs)
        texts.addWidget(label(title, "title", wrap=True))
        if message:
            msg = label(message, "muted", wrap=True)
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            texts.addWidget(msg)
        head.addLayout(texts, 1)
        root.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(SPACE.sm)
        root.addLayout(self.body)
        root.addSpacing(SPACE.sm)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(SPACE.sm)
        self.buttons.addStretch(1)
        root.addLayout(self.buttons)

    def add_button(self, key: str, text: str, variant: str = "", default: bool = False,
                   icon_name: str | None = None) -> QPushButton:
        b = button(text, icon_name, variant)
        b.setAutoDefault(default)
        b.setDefault(default)
        b.clicked.connect(lambda: self._finish(key))
        self.buttons.addWidget(b)
        if default:
            b.setFocus()
        return b

    def _finish(self, key: str) -> None:
        self.result_key = key
        self.accept() if key not in ("cancel",) else self.reject()

    def ask(self) -> str | None:
        self.exec()
        return self.result_key


def confirm(parent: QWidget, title: str, message: str, ok_text: str, danger: bool = False,
            icon_name: str = "alert") -> bool:
    dlg = StyledDialog(parent, title, message, icon_name, COLORS.error if danger else COLORS.warning)
    dlg.add_button("cancel", "Annuler")
    dlg.add_button("ok", ok_text, "danger" if danger else "primary", default=True)
    return dlg.ask() == "ok"


def inform(parent: QWidget, title: str, message: str, kind: str = "error") -> None:
    icon_name, color = {"error": ("x-circle", COLORS.error), "warning": ("alert", COLORS.warning)}.get(
        kind, ("info", COLORS.accent))
    dlg = StyledDialog(parent, title, message, icon_name, color)
    dlg.add_button("ok", "OK", "primary", default=True)
    dlg.ask()


def ask_unsaved_changes(parent: QWidget, show_name: str) -> str:
    """Retourne « save », « discard » ou « cancel »."""
    dlg = StyledDialog(
        parent,
        "Modifications non enregistrées",
        f"Le spectacle « {show_name} » a été modifié. Voulez-vous enregistrer les changements ?",
        "save",
        COLORS.warning,
    )
    dlg.add_button("cancel", "Annuler")
    dlg.add_button("discard", "Ne pas enregistrer", "ghost")
    dlg.add_button("save", "Enregistrer", "primary", default=True, icon_name="save")
    return dlg.ask() or "cancel"


def launch_check(parent: QWidget, issues: list[Issue]) -> bool:
    """Liste les problèmes avant d'entrer en projection. True : lancer quand même."""
    errors = [i for i in issues if i.severity is Severity.ERROR]
    title = "Vérification avant spectacle"
    if errors:
        message = (f"{len(errors)} séquence(s) ne pourront pas être lues. Pendant le spectacle, "
                   "elles afficheront leur image finale ou du noir, sans interrompre la conduite.")
        icon_name, color = "alert", COLORS.error
    else:
        message = "Le spectacle peut être lancé. Quelques points méritent votre attention :"
        icon_name, color = "alert", COLORS.warning
    dlg = StyledDialog(parent, title, message, icon_name, color, width=560)
    lst = QListWidget()
    lst.setObjectName("IssueList")
    lst.setSelectionMode(QListWidget.SelectionMode.NoSelection)
    lst.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    for issue in issues:
        item = QListWidgetItem(icons.icon("x-circle" if issue.severity is Severity.ERROR else "alert",
                                          COLORS.error if issue.severity is Severity.ERROR else COLORS.warning),
                               issue.message)
        lst.addItem(item)
    lst.setMinimumHeight(min(260, 34 * len(issues) + 12))
    dlg.body.addWidget(lst)
    dlg.add_button("cancel", "Revenir à la préparation", default=bool(errors))
    dlg.add_button("ok", "Lancer quand même", "primary", default=not errors, icon_name="play")
    return dlg.ask() == "ok"


def ask_recovery(parent: QWidget | None, entry: RecoveryEntry) -> str:
    """Retourne « restore », « discard » ou « later »."""
    when = entry.saved_at.astimezone().strftime("%d/%m/%Y à %H:%M")
    dlg = StyledDialog(
        parent,
        "Récupération après incident",
        f"Régie Vidéo ne s'est pas fermé normalement. Une copie de secours du spectacle "
        f"« {entry.show_name} » ({entry.cue_count} séquence(s)) a été enregistrée le {when}.",
        "restart",
        COLORS.accent,
    )
    if entry.project_path:
        dlg.body.addWidget(label(f"Fichier d'origine : {entry.project_path}", "caption", wrap=True))
    dlg.add_button("discard", "Supprimer la copie", "ghost")
    dlg.add_button("later", "Plus tard")
    dlg.add_button("restore", "Récupérer", "primary", default=True)
    return dlg.ask() or "later"


def now_text() -> str:
    return datetime.now().strftime("%H:%M")

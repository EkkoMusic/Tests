"""Composants réutilisables du design system."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.utils.paths import resource_path

from ..theme import icons
from ..theme.tokens import COLORS, SPACE


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def button(text: str, icon_name: str | None = None, variant: str = "", icon_color: str | None = None,
           tooltip: str = "") -> QPushButton:
    # Fusion colle l'icône au texte : une espace fine les sépare.
    b = QPushButton(f"\u2009 {text}" if icon_name and text else text)
    if variant:
        b.setProperty("variant", variant)
    if icon_name:
        color = icon_color or {
            "primary": COLORS.on_accent, "launch": COLORS.on_accent, "danger": COLORS.on_accent,
            "ghost": COLORS.text_2,
        }.get(variant, COLORS.text)
        b.setIcon(icons.icon(icon_name, color))
        b.setIconSize(QSize(16, 16))
    if tooltip:
        b.setToolTip(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def tool_button(icon_name: str, tooltip: str, size: int = 18, color: str = COLORS.text_2,
                variant: str = "") -> QToolButton:
    b = QToolButton()
    b.setIcon(icons.icon(icon_name, color))
    b.setIconSize(QSize(size, size))
    b.setToolTip(tooltip)
    b.setAccessibleName(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if variant:
        b.setProperty("variant", variant)
    return b


def label(text: str = "", role: str = "", wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    return lbl


def section_label(text: str) -> QLabel:
    return label(text.upper(), "section")


def icon_label(icon_name: str, color: str = COLORS.text_2, size: int = 16) -> QLabel:
    lbl = QLabel()
    lbl.setPixmap(icons.pixmap(icon_name, color, size))
    lbl.setFixedSize(size, size)
    return lbl


class Pill(QLabel):
    """Pastille d'état : success, error, warning, neutral, accent."""

    def __init__(self, text: str = "", kind: str = "neutral") -> None:
        super().__init__(text)
        self.set_kind(kind)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_kind(self, kind: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        self.setProperty("pill", kind)
        repolish(self)


def divider(vertical: bool = False) -> QFrame:
    f = QFrame()
    f.setObjectName("VDivider" if vertical else "Divider")
    return f


class Logo(QWidget):
    """Logo vectoriel de Régie Vidéo."""

    def __init__(self, size: int = 28, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(str(resource_path("icons", "logo.svg")), self)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._renderer.render(p)


class Toggle(QCheckBox):
    """Interrupteur animé (remplace la case à cocher)."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 24)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def hitButton(self, pos) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(1, 2, 38, 20)
        off, on = QColor(COLORS.surface_3), QColor(COLORS.accent)
        if not self.isEnabled():
            off, on = QColor(COLORS.surface_2), QColor(COLORS.text_3)
        t = self._pos
        color = QColor(
            round(off.red() + (on.red() - off.red()) * t),
            round(off.green() + (on.green() - off.green()) * t),
            round(off.blue() + (on.blue() - off.blue()) * t),
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(track, 10, 10)
        if self.hasFocus():
            p.setPen(QPen(QColor(COLORS.accent_hover), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(track.adjusted(-0.5, -0.5, 0.5, 0.5), 10.5, 10.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        x = 4 + t * 18
        p.drawEllipse(QRectF(x, 5, 14, 14))


class SegmentedControl(QFrame):
    """Choix exclusif présenté comme un groupe de segments."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str, str | None]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for value, text, icon_name in options:
            b = button(text, icon_name, "segment", icon_color=COLORS.text_2)
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._group.addButton(b)
            self._buttons[value] = b
            layout.addWidget(b)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))

    def set_value(self, value: str) -> None:
        b = self._buttons.get(value)
        if b is not None:
            b.setChecked(True)

    def value(self) -> str:
        for value, b in self._buttons.items():
            if b.isChecked():
                return value
        return ""


class Toast(QFrame):
    """Notification discrète et non bloquante (mode préparation uniquement)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE.lg, SPACE.md, SPACE.lg, SPACE.md)
        layout.setSpacing(SPACE.sm)
        self._icon = QLabel()
        self._text = QLabel()
        layout.addWidget(self._icon)
        layout.addWidget(self._text)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_anim_finished)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text: str, kind: str = "success", duration_ms: int = 2600) -> None:
        icon_name, color = {
            "success": ("check-circle", COLORS.success),
            "error": ("x-circle", COLORS.error),
            "warning": ("alert", COLORS.warning),
        }.get(kind, ("info", COLORS.accent))
        self._icon.setPixmap(icons.pixmap(icon_name, color, 18))
        self._text.setText(text)
        self.adjustSize()
        self._reposition()
        self.raise_()
        self.show()
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity() if self.isVisible() else 0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(duration_ms)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if self._anim.endValue() == 0.0:
            self.hide()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 56)


class EmptyState(QWidget):
    """État vide de la conduite, invitant à ajouter la première vidéo."""

    addRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.xl)
        zone = QFrame()
        zone.setObjectName("DropZone")
        outer.addWidget(zone)
        layout = QVBoxLayout(zone)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACE.md)
        badge = QLabel()
        badge.setPixmap(icons.pixmap("film", COLORS.accent, 44))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = label("Votre conduite est vide", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = label(
            "Ajoutez les vidéos de présentation des artistes, dans l'ordre de passage.\n"
            "Vous pouvez aussi glisser-déposer des fichiers ici.",
            "muted",
            wrap=True,
        )
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cta = button("Ajouter ma première vidéo", "plus", "primary")
        cta.clicked.connect(self.addRequested)
        hint = label("Astuce : une image portant le même nom que la vidéo est associée automatiquement.", "caption", wrap=True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(badge)
        layout.addSpacing(SPACE.sm)
        layout.addWidget(title)
        layout.addWidget(text)
        layout.addSpacing(SPACE.md)
        layout.addWidget(cta, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(SPACE.sm)
        layout.addWidget(hint)
        layout.addStretch(1)

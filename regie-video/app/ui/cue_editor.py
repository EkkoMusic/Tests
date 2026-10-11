"""Panneau latéral : propriétés de la séquence sélectionnée."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.media.formats import IMAGE_FILTER, VIDEO_FILTER
from app.media.media_validator import FileStatus, image_status, video_status
from app.models import Cue, EndBehavior
from app.utils.timefmt import format_clock

from .media_panel import MediaInfoPanel
from .theme.tokens import COLORS, SPACE
from .widgets.common import Pill, SegmentedControl, button, icon_label, label, section_label


class PathField(QWidget):
    """Chemin de fichier en lecture seule + bouton de choix."""

    def __init__(self, button_text: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.sm)
        self.edit = QLineEdit()
        self.edit.setReadOnly(True)
        self.edit.setPlaceholderText("Aucun fichier")
        self.button = button(button_text, icon_name)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def set_path(self, path: str) -> None:
        self.edit.setText(path)
        self.edit.setToolTip(path)
        self.edit.setCursorPosition(len(path))


class Thumb(QFrame):
    """Cadre 16:9 noir affichant une image réduite."""

    def __init__(self, height: int = 140, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ThumbFrame")
        self.setFixedHeight(height)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)
        self._image: QImage | None = None
        self._placeholder = ""

    def set_image(self, image: QImage | None, placeholder: str = "") -> None:
        self._image = image if image is not None and not image.isNull() else None
        self._placeholder = placeholder
        self._refresh()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        if self._image is None:
            self._label.setPixmap(QPixmap())
            self._label.setText(self._placeholder)
            self._label.setStyleSheet(f"color: {COLORS.text_3};")
            return
        ratio = self.devicePixelRatioF()
        size = self._label.size() * ratio
        pix = QPixmap.fromImage(self._image.scaled(size, Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))
        pix.setDevicePixelRatio(ratio)
        self._label.setText("")
        self._label.setPixmap(pix)


class CueEditor(QWidget):
    """Formulaire d'édition. Chaque modification émet ``cueEdited``."""

    cueEdited = Signal(str, dict)        # id de la séquence, champs modifiés
    renamed = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cue: Cue | None = None
        self._loading = False

        self._stack = QStackedWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

        # État « rien de sélectionné »
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(icon_label("sliders", COLORS.text_3, 28), 0, Qt.AlignmentFlag.AlignCenter)
        msg = label("Sélectionnez une séquence\npour modifier ses propriétés.", "muted")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(msg)
        self._stack.addWidget(empty)

        # Formulaire
        scroll = QScrollArea()
        scroll.setObjectName("Transparent")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form = QWidget()
        form.setObjectName("Transparent")
        scroll.setWidget(form)
        self._stack.addWidget(scroll)
        lay = QVBoxLayout(form)
        lay.setContentsMargins(SPACE.lg, SPACE.md, SPACE.lg, SPACE.lg)
        lay.setSpacing(SPACE.sm)

        # Nom
        lay.addWidget(section_label("Séquence"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nom de l'artiste ou de la séquence")
        self.name_edit.setMaxLength(120)
        self.name_edit.editingFinished.connect(self._commit_name)
        lay.addWidget(self.name_edit)
        lay.addSpacing(SPACE.md)

        # Vidéo
        head = QHBoxLayout()
        head.addWidget(section_label("Vidéo"))
        head.addStretch(1)
        self.video_pill = Pill()
        head.addWidget(self.video_pill)
        lay.addLayout(head)
        self.video_field = PathField("Parcourir…", "folder-open")
        self.video_field.button.clicked.connect(self._choose_video)
        lay.addWidget(self.video_field)
        info = QGridLayout()
        info.setHorizontalSpacing(SPACE.lg)
        info.addWidget(label("Durée détectée", "caption"), 0, 0)
        self.duration_label = label("--:--", "mono")
        info.addWidget(self.duration_label, 1, 0)
        info.addWidget(label("Volume", "caption"), 0, 1)
        vol_row = QHBoxLayout()
        vol_row.setSpacing(SPACE.sm)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setAccessibleName("Volume de la séquence")
        self.volume_value = label("100 %", "mono")
        self.volume_value.setMinimumWidth(42)
        vol_row.addWidget(icon_label("volume", COLORS.text_3, 14))
        vol_row.addWidget(self.volume_slider, 1)
        vol_row.addWidget(self.volume_value)
        info.addLayout(vol_row, 1, 1)
        info.setColumnStretch(1, 1)
        lay.addLayout(info)
        self._volume_timer = QTimer(self)
        self._volume_timer.setSingleShot(True)
        self._volume_timer.setInterval(250)
        self._volume_timer.timeout.connect(self._commit_volume)
        self.volume_slider.valueChanged.connect(self._on_volume)
        lay.addSpacing(SPACE.md)

        # Fin de vidéo
        lay.addWidget(section_label("À la fin de la vidéo"))
        self.end_control = SegmentedControl([
            (EndBehavior.IMAGE.value, "Image", "image"),
            (EndBehavior.BLACK.value, "Noir", "square"),
            (EndBehavior.LAST_FRAME.value, "Figer", "freeze"),
        ])
        self.end_control.setToolTip(
            "Image : affiche l'image finale choisie.\n"
            "Noir : passe au noir.\n"
            "Figer : conserve la dernière image de la vidéo."
        )
        self.end_control.changed.connect(self._on_end_changed)
        lay.addWidget(self.end_control)
        self.end_help = label("", "caption", wrap=True)
        lay.addWidget(self.end_help)

        self.image_box = QWidget()
        ib = QVBoxLayout(self.image_box)
        ib.setContentsMargins(0, SPACE.xs, 0, 0)
        ib.setSpacing(SPACE.sm)
        ih = QHBoxLayout()
        ih.addWidget(label("Image finale", "caption"))
        ih.addStretch(1)
        self.image_pill = Pill()
        ih.addWidget(self.image_pill)
        ib.addLayout(ih)
        self.image_field = PathField("Choisir une image…", "image")
        self.image_field.button.clicked.connect(self._choose_image)
        ib.addWidget(self.image_field)
        self.image_thumb = Thumb(150)
        ib.addWidget(self.image_thumb)
        self.remove_image = button("Retirer l'image", "x", "ghost")
        self.remove_image.clicked.connect(lambda: self._emit({"image_path": ""}))
        ib.addWidget(self.remove_image, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self.image_box)
        lay.addSpacing(SPACE.lg)
        self.media_panel = MediaInfoPanel()
        lay.addWidget(self.media_panel)
        lay.addStretch(1)

        self._stack.setCurrentIndex(0)

    # --------------------------------------------------------------- données
    @property
    def cue(self) -> Cue | None:
        return self._cue

    def set_cue(self, cue: Cue | None, image_preview: QImage | None = None) -> None:
        self._cue = cue
        if cue is None:
            self._stack.setCurrentIndex(0)
            return
        self._loading = True
        self._stack.setCurrentIndex(1)
        if not self.name_edit.hasFocus() or self.name_edit.text() != cue.name:
            self.name_edit.setText(cue.name)
        self.video_field.set_path(cue.video_path)
        self.duration_label.setText(format_clock(cue.duration_ms))
        self.volume_slider.setValue(cue.volume)
        self.volume_value.setText(f"{cue.volume} %")
        self.end_control.set_value(cue.end_behavior.value)
        self._update_end_section(cue)
        self.image_field.set_path(cue.image_path)
        self.image_thumb.set_image(image_preview, "Aucune image" if not cue.image_path else "Image introuvable")
        self.remove_image.setVisible(bool(cue.image_path))
        self._update_pills(cue)
        self._loading = False

    def set_probe_error(self, message: str) -> None:
        if message:
            self.video_pill.set_kind("error", "Illisible")
            self.video_pill.setToolTip(message)

    def set_media(self, info, assessment, display, fit, analyzing: bool = False) -> None:
        self.media_panel.set_data(info, assessment, display, fit, analyzing)

    def focus_name(self) -> None:
        self.name_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.name_edit.selectAll()

    # --------------------------------------------------------------- interne
    def _update_pills(self, cue: Cue) -> None:
        status = video_status(cue)
        text = {
            FileStatus.OK: ("success", "Disponible"),
            FileStatus.EMPTY: ("neutral", "Aucune vidéo"),
            FileStatus.MISSING: ("error", "Introuvable"),
            FileStatus.UNREADABLE: ("error", "Illisible"),
            FileStatus.UNSUPPORTED: ("error", "Format non pris en charge"),
        }[status]
        self.video_pill.set_kind(*text)
        self.video_pill.setToolTip("")
        if cue.image_path:
            st = image_status(cue.image_path)
            self.image_pill.set_kind(*({FileStatus.OK: ("success", "Disponible")}.get(st, ("warning", "Introuvable"))))
            self.image_pill.show()
        else:
            self.image_pill.hide()

    def _update_end_section(self, cue: Cue) -> None:
        behavior = cue.end_behavior
        self.image_box.setVisible(behavior is EndBehavior.IMAGE)
        self.end_help.setText({
            EndBehavior.IMAGE: "L'image reste affichée jusqu'à votre prochaine commande."
                               + ("" if cue.image_path else " Sans image choisie, du noir est affiché."),
            EndBehavior.BLACK: "La projection passe au noir et attend votre prochaine commande.",
            EndBehavior.LAST_FRAME: "La dernière image de la vidéo reste figée à l'écran.",
        }[behavior])

    def _emit(self, fields: dict) -> None:
        if self._cue is not None and not self._loading:
            self.cueEdited.emit(self._cue.id, fields)

    def _commit_name(self) -> None:
        if self._cue is None or self._loading:
            return
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setText(self._cue.name)
            return
        if name != self._cue.name:
            self.renamed.emit(self._cue.id, name)

    def _on_volume(self, value: int) -> None:
        self.volume_value.setText(f"{value} %")
        if not self._loading:
            self._volume_timer.start()

    def _commit_volume(self) -> None:
        self._emit({"volume": self.volume_slider.value()})

    def _on_end_changed(self, value: str) -> None:
        self._emit({"end_behavior": EndBehavior(value)})

    def _start_dir(self, path: str) -> str:
        return str(Path(path).parent) if path else ""

    def _choose_video(self) -> None:
        if self._cue is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choisir la vidéo", self._start_dir(self._cue.video_path), VIDEO_FILTER)
        if path:
            self._emit({"video_path": str(Path(path)), "duration_ms": None})

    def _choose_image(self) -> None:
        if self._cue is None:
            return
        start = self._start_dir(self._cue.image_path or self._cue.video_path)
        path, _ = QFileDialog.getOpenFileName(self, "Choisir l'image finale", start, IMAGE_FILTER)
        if path:
            self._emit({"image_path": str(Path(path)), "end_behavior": EndBehavior.IMAGE})

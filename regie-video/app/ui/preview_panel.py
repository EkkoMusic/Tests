"""Zone de prévisualisation, totalement indépendante de la conduite réelle.

Elle possède son propre moteur de lecture : rien de ce qui s'y passe ne
modifie l'état du spectacle ni ne déclenche une autre séquence. Elle
reproduit la fin de séquence (image finale, noir ou image figée) pour
vérifier la transition avant la représentation.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSlider, QToolButton, QVBoxLayout, QWidget

from app.media.image_loader import read_image
from app.media.media_validator import FileStatus, video_status
from app.media.playback_engine import QtPlaybackEngine
from app.models import Cue, EndBehavior
from app.persistence.app_settings import FitMode
from app.utils.timefmt import format_clock

from .theme import icons
from .theme.tokens import COLORS, SPACE
from .widgets.common import label, tool_button
from .widgets.video_surface import VideoSurface


class _AspectBox(QWidget):
    """Conteneur qui garde son enfant au format 16:9."""

    def __init__(self, child: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._child = child
        child.setParent(self)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return round(width * 9 / 16)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(400, 225)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(160, 90)

    def resizeEvent(self, event) -> None:  # noqa: N802
        w, h = self.width(), self.height()
        cw = min(w, round(h * 16 / 9))
        ch = round(cw * 9 / 16)
        self._child.setGeometry((w - cw) // 2, (h - ch) // 2, cw, ch)


class PreviewPanel(QWidget):
    durationDetected = Signal(str, int)  # id de séquence, durée

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cue: Cue | None = None
        self._token = 0
        self._ended = False
        self._seeking = False

        self.engine = QtPlaybackEngine(self)
        self.surface = VideoSurface(background=None)
        self.surface.set_fit_mode(FitMode.FIT)
        self.engine.frameReady.connect(self.surface.set_video_frame)
        self.engine.positionChanged.connect(self._on_position)
        self.engine.durationChanged.connect(self._on_duration)
        self.engine.playingChanged.connect(self._on_playing)
        self.engine.ended.connect(self._on_ended)
        self.engine.failed.connect(self._on_failed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.lg, SPACE.md, SPACE.lg, SPACE.md)
        layout.setSpacing(SPACE.sm)
        layout.addWidget(_AspectBox(self.surface), 1)

        self.message = label("", "caption")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.message)

        # Barre de progression + temps
        progress = QHBoxLayout()
        progress.setSpacing(SPACE.sm)
        self.elapsed = label("00:00", "mono")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setAccessibleName("Position de lecture")
        self.slider.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self.slider.sliderReleased.connect(self._seek_release)
        self.total = label("00:00", "mono")
        progress.addWidget(self.elapsed)
        progress.addWidget(self.slider, 1)
        progress.addWidget(self.total)
        layout.addLayout(progress)

        # Commandes
        controls = QHBoxLayout()
        controls.setSpacing(SPACE.xs)
        self.restart_btn = tool_button("restart", "Recommencer", 18)
        self.restart_btn.clicked.connect(self.restart)
        self.play_btn = QToolButton()
        self.play_btn.setProperty("variant", "round")
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.setIconSize(QSize(16, 16))
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self.toggle_play)
        self.end_btn = tool_button("image", "Afficher la fin de séquence", 18)
        self.end_btn.clicked.connect(self.show_end)
        self.mute_icon = tool_button("volume", "Couper / rétablir le son", 16)
        self.mute_icon.clicked.connect(self._toggle_mute)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(96)
        self.volume.setAccessibleName("Volume de prévisualisation")
        self.volume.valueChanged.connect(self._apply_volume)
        controls.addWidget(self.restart_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.end_btn)
        controls.addStretch(1)
        controls.addWidget(self.mute_icon)
        controls.addWidget(self.volume)
        layout.addLayout(controls)

        self._muted = False
        self._set_play_icon(False)
        self.set_cue(None)

    # ------------------------------------------------------------- public
    def set_preview_volume(self, value: int) -> None:
        self.volume.setValue(value)
        self._apply_volume()

    def set_cue(self, cue: Cue | None) -> None:
        """Charge une séquence (sans la lire)."""
        self.stop()
        self._cue = cue
        self.slider.setRange(0, 0)
        self.elapsed.setText("00:00")
        self.total.setText(format_clock(cue.duration_ms) if cue else "00:00")
        enabled = cue is not None and video_status(cue) is FileStatus.OK
        for w in (self.play_btn, self.restart_btn, self.slider):
            w.setEnabled(enabled)
        self.end_btn.setEnabled(cue is not None)
        if cue is None:
            self.message.setText("Aucune séquence sélectionnée")
        elif not enabled:
            self.message.setText("Vidéo indisponible")
        else:
            self.message.setText("")
        self.surface.show_black()

    def set_poster(self, image) -> None:
        """Image d'aperçu (miniature) affichée tant que la vidéo n'est pas lue."""
        if self._token == 0 and image is not None and not image.isNull():
            self.surface.show_still(image)

    def refresh_cue(self, cue: Cue) -> None:
        if self._cue is not None and cue.id == self._cue.id and not self.engine.is_playing():
            self.set_cue(cue)

    def toggle_play(self) -> None:
        if self._cue is None:
            return
        if self.engine.is_playing():
            self.engine.pause()
            return
        if self._token == 0 or self._ended:
            self._load_and_play()
        else:
            self.engine.play()

    def restart(self) -> None:
        if self._cue is not None:
            self._load_and_play()

    def stop(self) -> None:
        self.engine.stop()
        self._token = 0
        self._ended = False
        self._set_play_icon(False)

    def show_end(self) -> None:
        """Affiche l'état de fin de la séquence, comme en projection."""
        if self._cue is None:
            return
        playing_frame = self.surface.mode.value == "video"
        self.engine.pause()
        behavior = self._cue.effective_end_behavior
        if behavior is EndBehavior.IMAGE:
            self.surface.show_still(read_image(self._cue.image_path))
        elif behavior is EndBehavior.LAST_FRAME and playing_frame:
            self.surface.hold_last_frame()
        else:
            self.surface.show_black()
        self.engine.stop()
        self._token = 0

    # ------------------------------------------------------------ interne
    def _load_and_play(self) -> None:
        assert self._cue is not None
        self._token += 1
        self._ended = False
        self.message.setText("")
        self.surface.begin_video()
        self.engine.load(self._cue.video_path, self._token)
        self._apply_volume()
        self.engine.play()

    def _apply_volume(self) -> None:
        cue_volume = (self._cue.volume / 100) if self._cue else 1.0
        self.engine.set_volume(0.0 if self._muted else self.volume.value() / 100 * cue_volume)
        self.mute_icon.setIcon(icons.icon("volume-x" if self._muted or self.volume.value() == 0 else "volume", COLORS.text_2))

    def _toggle_mute(self) -> None:
        self._muted = not self._muted
        self._apply_volume()

    def _set_play_icon(self, playing: bool) -> None:
        self.play_btn.setIcon(icons.icon("pause" if playing else "play", COLORS.on_accent))
        self.play_btn.setToolTip("Pause" if playing else "Lecture")

    def _on_playing(self, playing: bool) -> None:
        self._set_play_icon(playing)

    def _on_position(self, ms: int) -> None:
        if not self._seeking:
            self.slider.setValue(ms)
        self.elapsed.setText(format_clock(ms))

    def _on_duration(self, ms: int) -> None:
        self.slider.setRange(0, max(0, ms))
        self.total.setText(format_clock(ms))
        if self._cue is not None and ms > 0 and self._cue.duration_ms != ms:
            self.durationDetected.emit(self._cue.id, ms)

    def _seek_release(self) -> None:
        self._seeking = False
        if self._token == 0 or self._ended:
            self._load_and_play()
            self.engine.pause()
        self.engine.seek(self.slider.value())
        self._ended = False

    def _on_ended(self, token: int) -> None:
        if token != self._token or self._cue is None:
            return
        self._ended = True
        behavior = self._cue.effective_end_behavior
        if behavior is EndBehavior.IMAGE:
            self.surface.show_still(read_image(self._cue.image_path))
        elif behavior is EndBehavior.LAST_FRAME:
            self.surface.hold_last_frame()
        else:
            self.surface.show_black()
        self._set_play_icon(False)

    def _on_failed(self, token: int, message: str) -> None:
        if token != self._token:
            return
        self.surface.show_black()
        self.message.setText(f"Lecture impossible : {message}")
        self._set_play_icon(False)

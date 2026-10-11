"""Fenêtre de projection du mode spectacle.

Plein écran, sans bordure, curseur masqué, aucun contrôle : seul le média
destiné au public est dessiné. Aucune boîte de dialogue n'est jamais ouverte
depuis cette fenêtre ; les incidents sont journalisés et la projection
conserve une sortie visuelle maîtrisée (image finale ou noir).
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QEvent, QKeyCombination, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence, QScreen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from app import APP_NAME
from app.core.cue_state import ShowState
from app.core.keyboard_controller import ExitGuard, KeyboardController, ShowAction, bindings_from_config
from app.core.show_controller import ShowController
from app.media.image_loader import ImagePreloader
from app.media.media_validator import FileStatus, image_status
from app.media.playback_engine import PlaybackEngine, QtPlaybackEngine
from app.models import Cue, EndBehavior, EndOfShowBehavior, Show
from app.persistence.app_settings import AppSettings
from app.utils.power import keep_display_awake

from .widgets.video_surface import VideoSurface

log = logging.getLogger(__name__)


def key_event_text(event: QKeyEvent) -> str:
    """Texte portable d'une touche : « Right », « Space », « Ctrl+Shift+Q »."""
    key = Qt.Key(event.key())
    if key in (Qt.Key.Key_unknown, Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        return ""
    # Les flèches du pavé numérique portent le modificateur « Keypad » : on l'ignore.
    modifiers = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
    return QKeySequence(QKeyCombination(modifiers, key)).toString(QKeySequence.SequenceFormat.PortableText)


class ProjectionPresenter:
    """Traduit les ordres du contrôleur en affichage (implémente ShowOutput)."""

    def __init__(self, surface: VideoSurface, engine: PlaybackEngine, show: Show, settings: AppSettings) -> None:
        self.surface = surface
        self.engine = engine
        self.show = show
        self.settings = settings
        self.images = ImagePreloader()
        self._cues = show.cues
        self.images.preload(show.settings.standby_image_path)
        for cue in show.cues[:2]:
            self.images.preload(cue.image_path)
        engine.frameReady.connect(surface.set_video_frame)

    # --------------------------------------------------------- ShowOutput
    def show_standby(self) -> None:
        self.engine.stop()
        self._show_image_or_black(self.show.settings.standby_image_path)

    def play_cue(self, cue: Cue, token: int) -> None:
        if cue.effective_end_behavior is EndBehavior.IMAGE:
            self.images.preload(cue.image_path)  # prête bien avant la fin de la vidéo
        index = self.show.index_of(cue.id)
        if 0 <= index + 1 < len(self._cues):
            self.images.preload(self._cues[index + 1].image_path)
        self.engine.set_volume(cue.volume / 100 * self.settings.master_volume / 100)
        self.surface.begin_video()
        self.engine.load(cue.video_path, token)
        self.engine.play()

    def show_cue_end(self, cue: Cue, live: bool) -> None:
        behavior = cue.effective_end_behavior
        if behavior is EndBehavior.LAST_FRAME and live:
            self.surface.hold_last_frame()
        elif behavior is EndBehavior.IMAGE:
            self._show_image_or_black(cue.image_path)
        else:
            self.surface.show_black()
        if not live:
            self.engine.stop()

    def show_error(self, cue: Cue | None) -> None:
        if cue is not None and cue.end_behavior is EndBehavior.IMAGE:
            self._show_image_or_black(cue.image_path)
        else:
            self.surface.show_black()

    def show_end_of_show(self, behavior: EndOfShowBehavior) -> None:
        if behavior is EndOfShowBehavior.BLACK:
            self.surface.show_black()
        elif behavior is EndOfShowBehavior.STANDBY:
            self._show_image_or_black(self.show.settings.standby_image_path)

    def pause(self) -> None:
        self.engine.pause()

    def resume(self) -> None:
        self.engine.play()

    def stop(self) -> None:
        self.engine.stop()

    def set_blackout(self, enabled: bool) -> None:
        self.surface.set_blackout(enabled)

    # ------------------------------------------------------------- interne
    def _show_image_or_black(self, path: str) -> None:
        if path and image_status(path) is FileStatus.OK:
            image = self.images.get(path)
            if not image.isNull():
                self.surface.show_still(image)
                return
        self.surface.show_black()


class ProjectionWindow(QWidget):
    exited = Signal()
    stateChanged = Signal(str)

    def __init__(self, show: Show, settings: AppSettings, engine: PlaybackEngine | None = None) -> None:
        super().__init__(None)
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background: #000000;")

        self.surface = VideoSurface(self)
        self.surface.set_fit_mode(settings.fit)
        self.surface.setCursor(Qt.CursorShape.BlankCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.surface)

        self.engine = engine or QtPlaybackEngine(self)
        self.engine.set_audio_device(settings.audio_device_id)
        self.presenter = ProjectionPresenter(self.surface, self.engine, show, settings)
        self.controller = ShowController(show.cues, self.presenter, show.settings.end_of_show)
        self.controller.on_state_changed = lambda old, new: self.stateChanged.emit(new.value)
        self.engine.started.connect(self.controller.on_media_started)
        self.engine.ended.connect(self.controller.on_media_ended)
        self.engine.failed.connect(self.controller.on_media_error)

        self.keyboard = KeyboardController(
            bindings_from_config(settings.key_bindings), settings.effective_repeat_interval_ms
        )
        self.exit_guard = ExitGuard(confirm=settings.confirm_exit)
        self._screen_name = settings.projection_screen
        self._allow_close = False

    # ----------------------------------------------------------- cycle de vie
    def target_screen(self) -> QScreen:
        for screen in QGuiApplication.screens():
            if screen.name() == self._screen_name:
                return screen
        return QGuiApplication.primaryScreen()

    def start(self) -> None:
        screen = self.target_screen()
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.controller.start()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        keep_display_awake(True)
        log.info("Projection ouverte sur l'écran « %s » (%s)", screen.name(), screen.geometry())

    def leave(self) -> None:
        if self._allow_close:
            return
        self._allow_close = True
        self.engine.stop()
        self.presenter.images.shutdown()
        keep_display_awake(False)
        log.info("Sortie du mode spectacle (état : %s)", self.controller.state.value)
        self.close()
        self.exited.emit()

    # ---------------------------------------------------------------- clavier
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        action = self.keyboard.press(key_event_text(event), event.isAutoRepeat(), time.monotonic() * 1000)
        event.accept()
        if action is not None:
            self.dispatch(action)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        self.keyboard.release(key_event_text(event), event.isAutoRepeat())
        event.accept()

    def dispatch(self, action: ShowAction) -> None:
        if action is ShowAction.EXIT:
            if self.exit_guard.request(time.monotonic() * 1000):
                self.leave()
            else:
                log.info("Sortie demandée : appuyer une seconde fois pour confirmer")
            return
        self.exit_guard.cancel()
        handled = {
            ShowAction.GO: self.controller.go,
            ShowAction.PAUSE_TOGGLE: self.controller.toggle_pause,
            ShowAction.RESTART: self.controller.restart,
            ShowAction.BLACKOUT_TOGGLE: self.controller.toggle_blackout,
            ShowAction.BACK: self.controller.back,
        }[action]()
        log.info("Commande %s → %s (%s)", action.value, "exécutée" if handled else "ignorée", self.controller.state.value)

    # -------------------------------------------------------------- système
    def event(self, event: QEvent) -> bool:  # noqa: D401
        if event.type() == QEvent.Type.WindowDeactivate and not self._allow_close:
            # Les relâchements de touches sont perdus : on repart d'un état propre.
            self.keyboard.reset()
            log.warning("La fenêtre de projection a perdu le focus clavier")
        return super().event(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._allow_close:
            event.ignore()  # Alt+F4 ou fermeture système : refusée pendant le spectacle
            log.warning("Fermeture de la projection refusée (utiliser le raccourci de sortie)")
            return
        super().closeEvent(event)

    @property
    def state(self) -> ShowState:
        return self.controller.state

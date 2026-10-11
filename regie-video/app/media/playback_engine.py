"""Moteur de lecture vidéo.

``PlaybackEngine`` définit le contrat attendu par la projection et la
prévisualisation. ``QtPlaybackEngine`` l'implémente avec Qt Multimedia
(backend FFmpeg). Un autre moteur (libmpv par exemple) pourra être branché
sans toucher à la logique de conduite ni à l'interface.

Les images décodées ne sont pas affichées par un widget vidéo opaque : elles
sont transmises (``frameReady``) à une surface de projection unique, qui
dessine aussi les images fixes et le noir. C'est ce qui permet une transition
vidéo → image finale sans changement de widget, donc sans clignotement.
"""

from __future__ import annotations

import logging
import os
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import (
    QAudioDevice,
    QAudioOutput,
    QMediaDevices,
    QMediaMetaData,
    QMediaPlayer,
    QVideoFrame,
    QVideoSink,
)

from .telemetry import FrameTelemetry

log = logging.getLogger(__name__)

LOAD_TIMEOUT_MS = 12_000


class PlaybackEngine(QObject):
    """Contrat d'un moteur de lecture. Chaque chargement porte un jeton,
    renvoyé dans les signaux, pour écarter les événements périmés."""

    started = Signal(int)            # première image affichable (ou lecture audio commencée)
    ended = Signal(int)              # fin réelle du média (événement du moteur)
    failed = Signal(int, str)        # erreur de chargement ou de lecture
    frameReady = Signal(QVideoFrame)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    playingChanged = Signal(bool)

    def load(self, path: str, token: int) -> None: raise NotImplementedError
    def play(self) -> None: raise NotImplementedError
    def pause(self) -> None: raise NotImplementedError
    def stop(self) -> None: raise NotImplementedError
    def seek(self, position_ms: int) -> None: raise NotImplementedError
    def set_volume(self, volume: float) -> None: raise NotImplementedError
    def set_muted(self, muted: bool) -> None: raise NotImplementedError
    def set_muted(self, muted: bool) -> None:
        if self._audio is not None:
            self._audio.setMuted(muted)

    def set_audio_device(self, device_id: str) -> None: raise NotImplementedError
    def is_playing(self) -> bool: raise NotImplementedError
    def duration(self) -> int: raise NotImplementedError


def _error_message(error: QMediaPlayer.Error, detail: str) -> str:
    base = {
        QMediaPlayer.Error.ResourceError: "fichier introuvable ou illisible",
        QMediaPlayer.Error.FormatError: "format ou codec non pris en charge",
        QMediaPlayer.Error.NetworkError: "erreur d'accès au fichier",
        QMediaPlayer.Error.AccessDeniedError: "accès refusé",
    }.get(error, "erreur de lecture")
    return f"{base} ({detail})" if detail else base


class QtPlaybackEngine(PlaybackEngine):
    def __init__(self, parent: QObject | None = None, with_audio: bool = True) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._sink = QVideoSink(self)
        self._player.setVideoSink(self._sink)
        self._audio: QAudioOutput | None = None
        self._device_id = ""
        if with_audio:
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
            self._devices = QMediaDevices(self)
            self._devices.audioOutputsChanged.connect(self._on_audio_outputs_changed)
        self.telemetry = FrameTelemetry()
        self._token = 0
        self._started = False
        self._ended = False
        self._accept_frames = False
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._on_timeout)

        self._sink.videoFrameChanged.connect(self._on_frame)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(self._on_error)
        self._player.positionChanged.connect(lambda p: self.positionChanged.emit(int(p)))
        self._player.durationChanged.connect(lambda d: self.durationChanged.emit(int(d)))
        self._player.playbackStateChanged.connect(
            lambda s: self.playingChanged.emit(s == QMediaPlayer.PlaybackState.PlayingState)
        )

    # ------------------------------------------------------------- commandes
    def load(self, path: str, token: int) -> None:
        self._token = token
        self._started = False
        self._ended = False
        self._accept_frames = True
        self.telemetry.reset(launched_at=time.monotonic())
        self.telemetry.fps = None
        if not path or not os.path.isfile(path):
            # Erreur différée : l'appelant reçoit l'événement après son propre traitement.
            QTimer.singleShot(0, self, lambda t=token: self._fail(t, "fichier vidéo introuvable"))
            return
        # Source vidée puis redéfinie : force un vrai rechargement, même pour le
        # même fichier (« Recommencer »).
        self._player.setSource(QUrl())
        self._player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
        self._watchdog.start(LOAD_TIMEOUT_MS)

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()
        self.telemetry.interrupt()

    def stop(self) -> None:
        self._watchdog.stop()
        self._accept_frames = False
        self._player.stop()

    def seek(self, position_ms: int) -> None:
        self._ended = False
        self.telemetry.interrupt()
        self._player.setPosition(max(0, int(position_ms)))

    def set_volume(self, volume: float) -> None:
        if self._audio is not None:
            self._audio.setVolume(max(0.0, min(1.0, volume)))

    def set_muted(self, muted: bool) -> None:
        if self._audio is not None:
            self._audio.setMuted(muted)

    def set_audio_device(self, device_id: str) -> None:
        self._device_id = device_id or ""
        self._apply_audio_device()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def duration(self) -> int:
        return int(self._player.duration())

    def position(self) -> int:
        return int(self._player.position())

    def has_video(self) -> bool:
        return self._player.hasVideo()

    # ------------------------------------------------------------ événements
    def _on_frame(self, frame: QVideoFrame) -> None:
        # Qt émet une image invalide à l'arrêt et parfois juste avant la fin :
        # on l'ignore, la dernière image valide reste affichée.
        if not self._accept_frames or not frame.isValid():
            return
        self.telemetry.feed(time.monotonic(), frame.startTime())
        self.frameReady.emit(frame)
        if not self._started:
            self._mark_started()

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        S = QMediaPlayer.MediaStatus
        if status == S.LoadedMedia:
            rate = self._player.metaData().value(QMediaMetaData.Key.VideoFrameRate)
            try:
                self.telemetry.fps = float(rate) if rate else None
            except (TypeError, ValueError):
                self.telemetry.fps = None
        if status in (S.BufferedMedia, S.BufferingMedia) and not self._started and not self._player.hasVideo():
            if self.is_playing():
                self._mark_started()  # fichier sans piste vidéo
        elif status == S.EndOfMedia and not self._ended:
            self._ended = True
            self._watchdog.stop()
            if not self._started:
                self._mark_started()
            log.info("Fin de média (jeton %d) : %s", self._token, self.telemetry.report().summary_fr())
            self.ended.emit(self._token)
        elif status == S.InvalidMedia:
            self._fail(self._token, "fichier corrompu ou format non pris en charge")

    def _on_error(self, error: QMediaPlayer.Error, detail: str) -> None:
        if error != QMediaPlayer.Error.NoError:
            self._fail(self._token, _error_message(error, detail))

    def _on_timeout(self) -> None:
        if not self._started:
            self._fail(self._token, "délai de chargement dépassé")

    def _mark_started(self) -> None:
        self._started = True
        self._watchdog.stop()
        self.started.emit(self._token)

    def _fail(self, token: int, message: str) -> None:
        if token != self._token:
            return
        self._watchdog.stop()
        self._accept_frames = False
        log.error("Échec de lecture (jeton %d) : %s", token, message)
        self.failed.emit(token, message)

    # ------------------------------------------------------------------ audio
    def current_audio_device(self) -> QAudioDevice | None:
        return self._audio.device() if self._audio is not None else None

    def _apply_audio_device(self) -> None:
        if self._audio is None:
            return
        if not QMediaDevices.audioOutputs():
            log.error("Aucune sortie audio disponible : la vidéo sera lue sans son")
        device = QMediaDevices.defaultAudioOutput()
        if self._device_id:
            for candidate in QMediaDevices.audioOutputs():
                if bytes(candidate.id().data()).decode(errors="replace") == self._device_id:
                    device = candidate
                    break
            else:
                log.warning("Sortie audio choisie absente : sortie par défaut utilisée")
        self._audio.setDevice(device)

    def _on_audio_outputs_changed(self) -> None:
        # Périphérique débranché (casque, carte son USB…) : repli sur la sortie par défaut.
        log.warning("La liste des sorties audio a changé")
        self._apply_audio_device()


def audio_device_id(device: QAudioDevice) -> str:
    return bytes(device.id().data()).decode(errors="replace")

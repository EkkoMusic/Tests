"""Analyse des vidéos en préparation : durée, miniature, lisibilité.

Les fichiers sont traités un par un, en tâche de fond, par un lecteur Qt muet
qui ne sert qu'à cela (il est totalement indépendant de la projection et de
la prévisualisation). Un fichier qui ne produit aucune image dans le délai
imparti est signalé comme illisible : c'est ainsi que l'on détecte avant le
spectacle un codec non pris en charge ou un fichier corrompu.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QMediaPlayer, QVideoFrame, QVideoSink

from .image_loader import read_image

log = logging.getLogger(__name__)

THUMB_SIZE = QSize(480, 270)
PROBE_TIMEOUT_MS = 10_000


@dataclass
class ProbeResult:
    path: str
    ok: bool
    duration_ms: int | None = None
    thumbnail: QImage | None = None
    error: str = ""
    has_audio: bool = False


def _cache_key(path: str) -> tuple[str, float, int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (os.path.normcase(os.path.abspath(path)), st.st_mtime, st.st_size)


class ThumbnailService(QObject):
    probed = Signal(object)  # ProbeResult

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)  # pas de sortie audio : muet
        self._sink = QVideoSink(self)
        self._player.setVideoSink(self._sink)
        self._sink.videoFrameChanged.connect(self._on_frame)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(self._on_error)
        self._queue: deque[str] = deque()
        self._current: str | None = None
        self._duration: int | None = None
        self._seeked = False
        self._cache: dict[tuple, ProbeResult] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self._finish(False, "aucune image décodée : codec non pris en charge ou fichier endommagé"))

    def result_for(self, path: str) -> ProbeResult | None:
        key = _cache_key(path)
        return self._cache.get(key) if key else None

    def request(self, path: str, force: bool = False) -> None:
        if not path:
            return
        key = _cache_key(path)
        if key is None:
            return  # fichier absent : signalé par le validateur
        if not force and key in self._cache:
            self.probed.emit(self._cache[key])
            return
        if path != self._current and path not in self._queue:
            self._queue.append(path)
        if self._current is None:
            QTimer.singleShot(0, self, self._next)

    def pending(self) -> int:
        return len(self._queue) + (1 if self._current else 0)

    # ------------------------------------------------------------- interne
    def _next(self) -> None:
        if self._current is not None or not self._queue:
            return
        self._current = self._queue.popleft()
        self._duration = None
        self._seeked = False
        self._player.setSource(QUrl.fromLocalFile(os.path.abspath(self._current)))
        self._timer.start(PROBE_TIMEOUT_MS)

    def _on_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if self._current is None:
            return
        S = QMediaPlayer.MediaStatus
        if status == S.LoadedMedia:
            self._duration = int(self._player.duration()) or None
            if not self._player.hasVideo():
                self._finish(False, "aucune piste vidéo")
                return
            target = min(1000, int((self._duration or 0) * 0.1))
            self._player.setPosition(target)
            self._seeked = True
            self._player.play()
        elif status == S.InvalidMedia:
            self._finish(False, "fichier corrompu ou format non pris en charge")
        elif status == S.EndOfMedia:
            self._finish(False, "aucune image décodée")

    def _on_error(self, error: QMediaPlayer.Error, detail: str) -> None:
        if self._current is not None and error != QMediaPlayer.Error.NoError:
            self._finish(False, detail or "erreur de lecture")

    def _on_frame(self, frame: QVideoFrame) -> None:
        if self._current is None or not self._seeked or not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return
        thumb = image.scaled(THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._finish(True, "", thumb)

    def _finish(self, ok: bool, error: str, thumb: QImage | None = None) -> None:
        path = self._current
        if path is None:
            return
        self._timer.stop()
        self._current = None
        has_audio = self._player.hasAudio()
        self._player.stop()
        self._player.setSource(QUrl())
        result = ProbeResult(path, ok, self._duration, thumb, error, has_audio)
        if not ok:
            log.warning("Vidéo non lisible %s : %s", path, error)
        key = _cache_key(path)
        if key:
            self._cache[key] = result
        self.probed.emit(result)
        QTimer.singleShot(0, self, self._next)


def image_thumbnail(path: str, size: QSize = THUMB_SIZE) -> QImage:
    image = read_image(path, max_side=max(size.width(), size.height()) * 2)
    if image.isNull():
        return image
    return image.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

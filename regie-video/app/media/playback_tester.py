"""Test de lecture réel, invisible et inaudible.

Chaque vidéo est décodée par le vrai moteur de lecture, en temps réel, mais
les images ne sont envoyées vers aucun écran et le son est coupé : rien
n'est montré ni diffusé au public pendant le test. On mesure ce que le
moteur livre (voir ``telemetry``) ; le coût du dessin à l'écran n'est pas
inclus, d'où la recommandation de toujours faire une répétition réelle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal

from .playback_engine import QtPlaybackEngine
from .telemetry import PlaybackReport

log = logging.getLogger(__name__)


@dataclass
class PlaybackJob:
    key: str            # identifiant de la séquence
    path: str
    duration_ms: int | None


class PlaybackTester(QObject):
    progress = Signal(int, int, str)          # étape, total, description
    measured = Signal(str, object)            # clé, PlaybackReport
    finished = Signal()

    def __init__(self, passes: int = 2, max_seconds: float | None = 20, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.passes = max(1, passes)
        self.max_seconds = max_seconds
        self.engine = QtPlaybackEngine(self, with_audio=True)
        self.engine.set_volume(0.0)
        self.engine.set_muted(True)
        self.engine.ended.connect(self._on_end)
        self.engine.failed.connect(self._on_failed)
        self.engine.started.connect(self._on_started)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_time_limit)
        self._jobs: list[PlaybackJob] = []
        self._step = 0
        self._token = 0
        self._cancelled = False
        self._current: tuple[PlaybackJob, int] | None = None
        self._seek_to = 0

    def total_steps(self) -> int:
        return len(self._jobs) * self.passes

    def start(self, jobs: list[PlaybackJob]) -> None:
        self._jobs = list(jobs)
        self._step = 0
        self._cancelled = False
        QTimer.singleShot(0, self, self._next)

    def cancel(self) -> None:
        self._cancelled = True
        self._timer.stop()
        self.engine.stop()

    def _next(self) -> None:
        if self._cancelled:
            return
        if self._step >= self.total_steps():
            self.engine.stop()
            self.finished.emit()
            return
        job = self._jobs[self._step // self.passes]
        n = self._step % self.passes
        self._current = (job, n)
        self.progress.emit(self._step, self.total_steps(), f"{job.key}|{n + 1}")
        # Passages successifs à des positions différentes (début, milieu, fin).
        dur = job.duration_ms or 0
        limit = self.max_seconds * 1000 if self.max_seconds else None
        if n == 0 or not dur or (limit and dur <= limit):
            self._seek_to = 0
        else:
            span = dur - (limit or 0)
            self._seek_to = int(max(0, span) * n / max(1, self.passes - 1))
        self._token += 1
        self.engine.load(job.path, self._token)
        self.engine.play()

    def _on_started(self, token: int) -> None:
        if token != self._token or self._current is None:
            return
        if self._seek_to:
            self.engine.seek(self._seek_to)
            self.engine.telemetry.reset()  # la mesure commence après le déplacement
        if self.max_seconds:
            self._timer.start(int(self.max_seconds * 1000))

    def _finish_pass(self, report: PlaybackReport) -> None:
        self._timer.stop()
        job, _n = self._current
        self.measured.emit(job.key, report)
        self._step += 1
        self.engine.stop()
        QTimer.singleShot(150, self, self._next)

    def _on_end(self, token: int) -> None:
        if token == self._token and self._current is not None:
            self._finish_pass(self.engine.telemetry.report())

    def _on_time_limit(self) -> None:
        if self._current is not None:
            self._finish_pass(self.engine.telemetry.report())

    def _on_failed(self, token: int, message: str) -> None:
        if token == self._token and self._current is not None:
            log.warning("Test de lecture : échec (%s)", message)
            self._finish_pass(PlaybackReport())

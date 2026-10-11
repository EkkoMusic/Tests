"""Analyse des médias en arrière-plan (FFprobe dans des fils dédiés).

Rien de coûteux n'est exécuté sur le fil de l'interface : FFprobe tourne dans
un processus séparé, lancé depuis un fil d'arrière-plan, et le résultat
revient par un signal Qt.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal

from .media_info import MediaInfo, find_ffprobe, probe_file

log = logging.getLogger(__name__)


def _key(path: str) -> tuple | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return os.path.normcase(os.path.abspath(path)), st.st_mtime, st.st_size


class MediaAnalyzer(QObject):
    analyzed = Signal(object)   # MediaInfo
    _done = Signal(str, object)

    def __init__(self, parent: QObject | None = None, workers: int = 2) -> None:
        super().__init__(parent)
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ffprobe")
        self._cache: dict[tuple, MediaInfo] = {}
        self._pending: set[str] = set()
        self.ffprobe = find_ffprobe()
        if not self.ffprobe:
            log.warning("FFprobe introuvable : analyse limitée aux métadonnées Qt")
        self._done.connect(self._on_done)

    @property
    def available(self) -> bool:
        return self.ffprobe is not None

    def result_for(self, path: str) -> MediaInfo | None:
        key = _key(path)
        return self._cache.get(key) if key else None

    def pending(self) -> int:
        return len(self._pending)

    def request(self, path: str, force: bool = False) -> None:
        if not path or not self.available:
            return
        key = _key(path)
        if key is None:
            return
        if not force and key in self._cache:
            self.analyzed.emit(self._cache[key])
            return
        if path in self._pending:
            return
        self._pending.add(path)
        tool = self.ffprobe
        self._pool.submit(self._work, path, tool)

    def _work(self, path: str, tool: str) -> None:
        try:
            info = probe_file(path, tool)
        except Exception as exc:  # pragma: no cover - probe_file ne lève pas
            info = MediaInfo(path=path, error=str(exc))
        try:
            self._done.emit(path, info)
        except RuntimeError:
            pass  # objet détruit pendant l'analyse

    def _on_done(self, path: str, info: MediaInfo) -> None:
        self._pending.discard(path)
        key = _key(path)
        if key:
            self._cache[key] = info
        self.analyzed.emit(info)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

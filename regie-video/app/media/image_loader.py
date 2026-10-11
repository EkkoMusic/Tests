"""Chargement des images fixes (finales, attente) hors du fil de l'interface."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QImageReader

from .media_validator import FileStatus, image_status

log = logging.getLogger(__name__)


def read_image(path: str, max_side: int = 0) -> QImage:
    """Décode une image en respectant l'orientation EXIF. Image nulle en cas d'échec."""
    if not path or image_status(path) is not FileStatus.OK:
        return QImage()
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    if max_side:
        size = reader.size()
        if size.isValid() and max(size.width(), size.height()) > max_side:
            size.scale(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio)
            reader.setScaledSize(size)
    image = reader.read()
    if image.isNull():
        log.warning("Image illisible %s : %s", path, reader.errorString())
    return image


class ImagePreloader:
    """Décode les images en arrière-plan et les garde en mémoire.

    Le cache est volontairement petit : seules l'image d'attente et les
    images finales proches de la séquence en cours y séjournent.
    """

    def __init__(self, capacity: int = 6) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="images")
        self._cache: dict[str, Future] = {}
        self._capacity = capacity

    def preload(self, path: str) -> None:
        if not path or path in self._cache:
            return
        self._cache[path] = self._pool.submit(read_image, path)
        while len(self._cache) > self._capacity:
            self._cache.pop(next(iter(self._cache)))

    def get(self, path: str) -> QImage:
        if not path:
            return QImage()
        self.preload(path)
        try:
            return self._cache[path].result(timeout=5)
        except Exception:
            log.exception("Chargement d'image impossible : %s", path)
            return QImage()

    def clear(self) -> None:
        self._cache.clear()

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

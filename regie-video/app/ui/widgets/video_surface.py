"""Surface d'affichage unique pour la vidéo, les images fixes et le noir.

Tout est dessiné dans le même widget, par le même ``paintEvent`` : passer de
la dernière image de la vidéo à l'image finale consiste à changer la source
du prochain rafraîchissement. Pas de widget masqué/affiché, pas de fenêtre
native vidéo, donc pas de flash du bureau ni de clignotement.

Les proportions sont toujours respectées ; l'espace restant est noir.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtMultimedia import QVideoFrame
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.persistence.app_settings import FitMode


class SurfaceMode(str, Enum):
    BLACK = "black"
    VIDEO = "video"
    STILL = "still"


def target_rect(content: QSize, area: QRect, fit: FitMode, device_ratio: float = 1.0) -> QRectF:
    """Rectangle centré qui respecte les proportions du contenu.

    ``content`` est en pixels du média ; ``area`` en pixels logiques. En taille
    native, un pixel du média occupe un pixel physique de l'écran.
    """
    if content.isEmpty() or area.isEmpty():
        return QRectF(area)
    if fit is FitMode.NATIVE:
        w, h = content.width() / device_ratio, content.height() / device_ratio
        return QRectF(area.x() + (area.width() - w) / 2, area.y() + (area.height() - h) / 2, w, h)
    scaled = content.scaled(
        area.size(),
        Qt.AspectRatioMode.KeepAspectRatio if fit is FitMode.FIT else Qt.AspectRatioMode.KeepAspectRatioByExpanding,
    )
    x = area.x() + (area.width() - scaled.width()) / 2
    y = area.y() + (area.height() - scaled.height()) / 2
    return QRectF(x, y, scaled.width(), scaled.height())


class VideoSurface(QWidget):
    """Rendu « Compatibilité » : conversion et dessin par le processeur."""

    renderer_name = "Compatibilité (processeur)"
    def __init__(self, parent: QWidget | None = None, background: QColor | None = None) -> None:
        super().__init__(parent)
        self._background = background or QColor(0, 0, 0)
        self._mode = SurfaceMode.BLACK
        self._frame: QVideoFrame | None = None
        self._still: QImage | None = None
        self._still_scaled: QPixmap | None = None
        self._still_scaled_key: tuple | None = None
        self._pending_video = False
        self._blackout = False
        self._fit = FitMode.FIT
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    # ---------------------------------------------------------------- état
    @property
    def mode(self) -> SurfaceMode:
        return self._mode

    @property
    def blackout(self) -> bool:
        return self._blackout

    def set_fit_mode(self, fit: FitMode) -> None:
        self._fit = fit
        self._still_scaled = None
        self.update()

    # ------------------------------------------------------------- contenu
    def begin_video(self) -> None:
        """Une vidéo va démarrer : l'affichage actuel reste en place jusqu'à
        sa première image, ce qui évite tout noir entre deux séquences."""
        self._pending_video = True

    def set_video_frame(self, frame: QVideoFrame) -> None:
        if not frame.isValid():
            return
        if self._mode is not SurfaceMode.VIDEO and not self._pending_video:
            return  # image tardive d'une vidéo déjà terminée
        self._pending_video = False
        self._frame = QVideoFrame(frame)
        self._mode = SurfaceMode.VIDEO
        self.update()

    def hold_last_frame(self) -> bool:
        """Fige la dernière image vidéo (copiée en mémoire)."""
        if self._frame is None:
            self.show_black()
            return False
        image = self._frame.toImage()
        self._frame = None
        if image.isNull():
            self.show_black()
            return False
        self.show_still(image)
        return True

    def prepare_still(self, image: QImage | None) -> None:
        """Prépare la mise à l'échelle d'une image avant son affichage."""
        if image is not None and not image.isNull():
            self._scaled_pixmap(image)

    def show_still(self, image: QImage | None) -> None:
        if image is None or image.isNull():
            self.show_black()
            return
        self._pending_video = False
        self._frame = None
        self._still = image
        self._mode = SurfaceMode.STILL
        self.update()

    def show_black(self) -> None:
        self._pending_video = False
        self._frame = None
        self._still = None
        self._mode = SurfaceMode.BLACK
        self.update()

    def set_blackout(self, enabled: bool) -> None:
        self._blackout = enabled
        self.repaint()  # immédiat, sans attendre la boucle d'événements

    def current_image(self) -> QImage | None:
        """Image actuellement à l'écran (pour les tests et la prévisualisation)."""
        if self._mode is SurfaceMode.STILL:
            return self._still
        if self._mode is SurfaceMode.VIDEO and self._frame is not None:
            return self._frame.toImage()
        return None

    # --------------------------------------------------------------- rendu
    def _scaled_pixmap(self, image: QImage) -> QPixmap:
        ratio = self.devicePixelRatioF()
        area = self.rect()
        key = (image.cacheKey(), area.width(), area.height(), ratio, self._fit)
        if self._still_scaled is not None and self._still_scaled_key == key:
            return self._still_scaled
        rect = target_rect(image.size(), area, self._fit, ratio)
        size = QSize(max(1, round(rect.width() * ratio)), max(1, round(rect.height() * ratio)))
        pixmap = QPixmap.fromImage(
            image.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        pixmap.setDevicePixelRatio(ratio)
        self._still_scaled, self._still_scaled_key = pixmap, key
        return pixmap

    def paintEvent(self, event) -> None:  # noqa: N802 (API Qt)
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black if self._blackout else self._background)
        if self._blackout:
            return
        if self._mode is SurfaceMode.STILL and self._still is not None:
            pixmap = self._scaled_pixmap(self._still)
            rect = target_rect(self._still.size(), self.rect(), self._fit, self.devicePixelRatioF())
            painter.fillRect(rect, Qt.GlobalColor.black)
            painter.drawPixmap(rect.topLeft(), pixmap)
        elif self._mode is SurfaceMode.VIDEO and self._frame is not None:
            image = self._frame.toImage()  # conversion uniquement des images réellement peintes
            if not image.isNull():
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                rect = target_rect(image.size(), self.rect(), self._fit, self.devicePixelRatioF())
                painter.fillRect(rect, Qt.GlobalColor.black)
                painter.drawImage(rect, image)

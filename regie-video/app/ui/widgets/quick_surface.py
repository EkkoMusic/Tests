"""Surface de projection accélérée par la carte graphique (Qt Quick).

Même interface que :class:`VideoSurface` (rendu processeur), mais :

* les images décodées sont confiées telles quelles au ``VideoOutput`` de Qt
  Quick : pas de conversion en QImage, pas de mise à l'échelle par le
  processeur, pas de recopie GPU → CPU quand le décodage est matériel. La
  conversion YUV → RVB (matrices BT.601/709/2020, plage limitée/complète,
  transfert HDR) est faite par les shaders de Qt Multimedia ;
* vidéo, image fixe et noir sont des couches d'une même scène : la bascule
  est atomique ;
* l'image vide que Qt émet en fin de média n'est jamais transmise, donc la
  dernière image reste affichée jusqu'à l'image finale.
"""

from __future__ import annotations

import itertools
import logging

from PySide6.QtCore import QObject, QSize, QSizeF, Qt, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QVideoFrame, QVideoSink
from PySide6.QtQuick import QQuickImageProvider, QQuickWindow
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.persistence.app_settings import FitMode
from app.utils.paths import resource_path

from .video_surface import SurfaceMode, target_rect

log = logging.getLogger(__name__)

_FIT_INDEX = {FitMode.FIT: 0, FitMode.FILL: 1, FitMode.NATIVE: 2}
_provider_ids = itertools.count(1)


class _StillProvider(QQuickImageProvider):
    """Fournit à la scène les images fixes déjà décodées en mémoire."""

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._images: dict[str, QImage] = {}

    def put(self, key: str, image: QImage) -> None:
        self._images[key] = image
        # Seules les deux dernières images (affichée + préchargée) sont gardées.
        while len(self._images) > 3:
            self._images.pop(next(iter(self._images)))

    def requestImage(self, image_id: str, size, requested_size) -> QImage:  # noqa: N802
        image = self._images.get(image_id.split("?")[0], QImage())
        if size is not None:
            try:
                size.setWidth(image.width())
                size.setHeight(image.height())
            except AttributeError:
                pass
        return image


def make_prescaler(area, ratio: float, fit: FitMode):
    """Réduit une image à sa taille d'affichage exacte, avec un filtre lissé.

    Les images ne sont jamais agrandies par le processeur, et une image déjà à
    la bonne taille est rendue telle quelle (aucun second filtrage).
    """
    area = area.__class__(area)

    def prescale(image: QImage) -> QImage:
        if fit is FitMode.NATIVE or area.width() <= 0 or image.isNull():
            return image
        rect = target_rect(image.size(), area, fit, ratio)
        size = QSize(max(1, round(rect.width() * ratio)), max(1, round(rect.height() * ratio)))
        if size.width() >= image.width() or size.height() >= image.height():
            return image
        scaled = image.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return scaled

    return prescale


class QuickVideoSurface(QQuickWidget):
    """Surface vidéo GPU. Voir le module pour les garanties."""

    renderer_name = "Accéléré (carte graphique)"
    failed = Signal(str)

    def __init__(self, parent: QWidget | None = None, background=None) -> None:
        super().__init__(parent)
        self._mode = SurfaceMode.BLACK
        self._blackout = False
        self._fit = FitMode.FIT
        self._pending_video = False
        self._last_frame: QVideoFrame | None = None
        self._still: QImage | None = None
        self._still_seq = itertools.count(1)
        self._provider_name = f"stills{next(_provider_ids)}"
        self._provider = _StillProvider()
        self.engine().addImageProvider(self._provider_name, self._provider)
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.setClearColor(Qt.GlobalColor.black)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setSource(QUrl.fromLocalFile(str(resource_path("qml", "ProjectionSurface.qml"))))
        if self.status() != QQuickWidget.Status.Ready or self.rootObject() is None:
            errors = "; ".join(e.toString() for e in self.errors())
            raise RuntimeError(f"Surface Qt Quick indisponible : {errors or self.status()}")
        self._root = self.rootObject()
        video = self._root.findChild(QObject, "video")
        self._output_sink: QVideoSink = video.property("videoSink")
        if self._output_sink is None:
            raise RuntimeError("VideoOutput sans videoSink")
        self.sceneGraphError.connect(self._on_scene_error)

    # ---------------------------------------------------------------- état
    @property
    def mode(self) -> SurfaceMode:
        return self._mode

    @property
    def blackout(self) -> bool:
        return self._blackout

    def graphics_api(self) -> str:
        window = self.quickWindow()
        api = window.rendererInterface().graphicsApi() if window and window.rendererInterface() else QQuickWindow.graphicsApi()
        return getattr(api, "name", str(api))

    def set_fit_mode(self, fit: FitMode) -> None:
        self._fit = fit
        self._root.setProperty("fitMode", _FIT_INDEX[fit])
        self._update_native_sizes()
        if self._still is not None and self._mode is SurfaceMode.STILL:
            self.show_still(self._still)

    def _set_mode(self, mode: SurfaceMode) -> None:
        self._mode = mode
        self._root.setProperty("mode", mode.value)

    # ------------------------------------------------------------- contenu
    def begin_video(self) -> None:
        self._pending_video = True

    def set_video_frame(self, frame: QVideoFrame) -> None:
        if not frame.isValid():
            return  # l'image vide de fin de média n'atteint jamais l'écran
        if self._mode is not SurfaceMode.VIDEO and not self._pending_video:
            return
        first = self._pending_video
        self._pending_video = False
        self._last_frame = frame
        self._output_sink.setVideoFrame(frame)  # aucune copie : la texture est partagée
        if first:
            self._native_video = frame.size()
            self._update_native_sizes()
            self._set_mode(SurfaceMode.VIDEO)

    def hold_last_frame(self) -> bool:
        """La dernière image reste dans le VideoOutput (aucune image vide n'est transmise)."""
        if self._last_frame is None:
            self.show_black()
            return False
        self._pending_video = False
        self._set_mode(SurfaceMode.VIDEO)
        return True

    def prepare_still(self, image: QImage | None) -> None:
        if image is None or image.isNull():
            return
        key = self._store(image)
        self._root.setProperty("stillPreload", f"image://{self._provider_name}/{key}")

    def show_still(self, image: QImage | None) -> None:
        if image is None or image.isNull():
            self.show_black()
            return
        self._pending_video = False
        self._still = image
        key = self._store(image)
        self._still_native = image.size()
        self._update_native_sizes()
        self._root.setProperty("stillSource", f"image://{self._provider_name}/{key}")
        self._set_mode(SurfaceMode.STILL)

    def show_black(self) -> None:
        self._pending_video = False
        self._still = None
        self._set_mode(SurfaceMode.BLACK)

    def set_blackout(self, enabled: bool) -> None:
        self._blackout = enabled
        self._root.setProperty("blackout", enabled)

    def current_image(self) -> QImage | None:
        if self._mode is SurfaceMode.STILL:
            return self._still
        if self._mode is SurfaceMode.VIDEO and self._last_frame is not None:
            return self._last_frame.toImage()
        return None

    def grab_image(self) -> QImage:
        """Rendu réel de la scène (tests, diagnostic)."""
        return self.grabFramebuffer()

    # ------------------------------------------------------------- interne
    def _store(self, image: QImage) -> str:
        """Met l'image à la taille exacte d'affichage (filtre lissé, une seule fois)."""
        prepared = self._prescale(image)
        key = str(next(self._still_seq))
        self._provider.put(key, prepared)
        return key

    def _prescale(self, image: QImage) -> QImage:
        return self.prescaler()(image)

    def prescaler(self):
        """Fonction de mise à l'échelle utilisable dans un autre fil (valeurs figées)."""
        return make_prescaler(self.rect(), self.devicePixelRatioF(), self._fit)

    def _update_native_sizes(self) -> None:
        ratio = self.devicePixelRatioF() or 1.0
        video = getattr(self, "_native_video", None)
        still = getattr(self, "_still_native", None)
        if video is not None:
            self._root.setProperty("nativeSize", QSizeF(video.width() / ratio, video.height() / ratio))
        if still is not None:
            self._root.setProperty("stillNativeSize", QSizeF(still.width() / ratio, still.height() / ratio))

    def _on_scene_error(self, error, message: str) -> None:
        log.error("Erreur du rendu GPU : %s", message)
        self.failed.emit(message)

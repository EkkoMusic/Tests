"""Surface de projection accélérée (Qt Quick).

Ces tests ont besoin d'un vrai rendu graphique (OpenGL, Direct3D…). Ils sont
ignorés en affichage virtuel « offscreen » ; ils tournent localement sous Xvfb
et sur la CI Windows (rendu Direct3D 11 logiciel WARP).
"""

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage

from app.core.cue_state import ShowState
from app.models import Cue, EndBehavior, Show
from app.persistence.app_settings import AppSettings, FitMode
from app.ui.projection_window import ProjectionWindow
from app.ui.widgets.video_surface import SurfaceMode

pytestmark = [pytest.mark.media, pytest.mark.gpu]


def _render_works() -> bool:
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return False
    try:
        from app.ui.widgets.quick_surface import QuickVideoSurface

        s = QuickVideoSurface()
        s.resize(64, 36)
        s.show()
        img = QImage(16, 9, QImage.Format.Format_RGB32)
        img.fill(QColor(255, 0, 0))
        s.show_still(img)
        grab = s.grab_image()
        ok = not grab.isNull() and grab.pixelColor(32, 18).red() > 200
        s.close()
        return ok
    except Exception:
        return False


@pytest.fixture(scope="module")
def gpu_available(qapp):
    if not _render_works():
        pytest.skip("Rendu Qt Quick indisponible dans cet environnement")


def color_at(img: QImage, x: int, y: int) -> tuple[int, int, int]:
    c = img.pixelColor(x, y)
    return c.red(), c.green(), c.blue()


@pytest.fixture
def surface(qtbot, gpu_available):
    from app.ui.widgets.quick_surface import QuickVideoSurface

    s = QuickVideoSurface()
    s.resize(640, 360)
    s.show()
    qtbot.addWidget(s)
    return s


def test_wide_still_is_letterboxed_not_stretched(surface):
    img = QImage(3289, 1480, QImage.Format.Format_RGB32)
    img.fill(QColor(0, 200, 0))
    surface.set_fit_mode(FitMode.FIT)
    surface.show_still(img)
    g = surface.grab_image()
    # 3289×1480 dans 640×360 : image de 640×288, bandes noires de 36 px en haut et en bas.
    assert color_at(g, 320, 10) == (0, 0, 0)
    assert color_at(g, 320, g.height() - 10) == (0, 0, 0)
    assert color_at(g, 320, 180)[1] > 180
    assert color_at(g, 5, 180)[1] > 180  # pleine largeur


def test_fill_mode_crops_without_bands(surface):
    img = QImage(3289, 1480, QImage.Format.Format_RGB32)
    img.fill(QColor(0, 200, 0))
    surface.set_fit_mode(FitMode.FILL)
    surface.show_still(img)
    g = surface.grab_image()
    assert color_at(g, 320, 3)[1] > 180


def test_native_mode_keeps_one_to_one_pixels(surface):
    img = QImage(100, 50, QImage.Format.Format_RGB32)
    img.fill(QColor(0, 0, 220))
    surface.set_fit_mode(FitMode.NATIVE)
    surface.show_still(img)
    g = surface.grab_image()
    ratio = surface.devicePixelRatioF()
    cx, cy = g.width() // 2, g.height() // 2
    assert color_at(g, cx, cy)[2] > 200
    assert color_at(g, cx + int(60 * ratio), cy) == (0, 0, 0)


def test_blackout_layer(surface):
    img = QImage(32, 18, QImage.Format.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    surface.show_still(img)
    surface.set_blackout(True)
    assert color_at(surface.grab_image(), 320, 180) == (0, 0, 0)
    surface.set_blackout(False)
    assert color_at(surface.grab_image(), 320, 180)[0] > 200


def test_projection_end_of_video_keeps_last_frame_then_final_image(qtbot, gpu_available, fixtures_dir):
    cue = Cue(name="A", video_path=str(fixtures_dir / "clip_silent.mp4"), image_path=str(fixtures_dir / "final_red.png"))
    show = Show(cues=[cue, Cue(name="B", video_path=str(fixtures_dir / "clip_silent.mp4"),
                               end_behavior=EndBehavior.LAST_FRAME)])
    win = ProjectionWindow(show, AppSettings(renderer="gpu", repeat_interval_ms=0))
    win.engine.set_volume(0)
    win.start()
    try:
        assert type(win.surface).__name__ == "QuickVideoSurface"
        win.dispatch(win.keyboard.bindings["Right"])
        qtbot.waitUntil(lambda: win.state is ShowState.PLAYING, timeout=15000)
        qtbot.waitUntil(lambda: win.surface.mode is SurfaceMode.VIDEO, timeout=5000)
        frame = win.surface.grab_image()
        assert color_at(frame, frame.width() // 2, frame.height() // 2) != (0, 0, 0)
        qtbot.waitUntil(lambda: win.state is ShowState.HOLDING, timeout=15000)
        g = win.surface.grab_image()
        r, gr, b = color_at(g, g.width() // 2, g.height() // 2)
        assert r > 200 and gr < 60 and b < 60  # image finale rouge
        win.dispatch(win.keyboard.bindings["Right"])
        qtbot.waitUntil(lambda: win.state is ShowState.HOLDING and win.controller.position == 1, timeout=15000)
        last = win.surface.grab_image()
        assert color_at(last, last.width() // 2, last.height() // 2) != (0, 0, 0)  # dernière image figée
    finally:
        win.leave()

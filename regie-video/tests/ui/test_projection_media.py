"""Tests d'intégration du mode spectacle avec le vrai moteur Qt Multimedia.

Ils utilisent de très courts fichiers (tests/fixtures) et l'affichage
« offscreen » : ils valident l'enchaînement des événements du moteur, pas le
rendu sur un vidéoprojecteur (voir docs/PROTOCOLE_TESTS.md).
"""

import shutil

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent

from app.core.cue_state import ShowState
from app.models import Cue, EndBehavior, EndOfShowBehavior, Show
from app.persistence.app_settings import AppSettings
from app.ui.projection_window import ProjectionWindow
from app.ui.widgets.video_surface import SurfaceMode

pytestmark = pytest.mark.media
TIMEOUT = 15000


@pytest.fixture
def media(fixtures_dir, tmp_path):
    for f in fixtures_dir.iterdir():
        if f.is_file():
            shutil.copy(f, tmp_path / f.name)
    return tmp_path


def make_window(qtbot, cues, **settings_kw):
    settings_kw.setdefault("renderer", "cpu")  # rendu vérifiable pixel par pixel hors écran
    settings = AppSettings(confirm_exit=True, repeat_interval_ms=100, **settings_kw)
    show = Show(name="Test", cues=cues)
    show.settings.end_of_show = EndOfShowBehavior.BLACK
    win = ProjectionWindow(show, settings)
    win.engine.set_volume(0)
    qtbot.addWidget(win)
    win.start()
    return win


def press(win, key, mods=Qt.KeyboardModifier.NoModifier):
    win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, mods))
    win.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, key, mods))
    win.keyboard._last_fired.clear()  # pas de délai anti-rebond entre deux appuis du test


def wait_state(qtbot, win, state):
    qtbot.waitUntil(lambda: win.state is state, timeout=TIMEOUT)


def center_color(win) -> QColor:
    image = win.surface.grab().toImage()
    return QColor(image.pixel(image.width() // 2, image.height() // 2))


def test_video_then_final_image_and_manual_go(qtbot, media):
    cues = [
        Cue(name="A", video_path=str(media / "clip_audio.mp4"), image_path=str(media / "final_red.png")),
        Cue(name="B", video_path=str(media / "clip_silent.mp4"), end_behavior=EndBehavior.BLACK),
    ]
    win = make_window(qtbot, cues)
    assert win.state is ShowState.IDLE
    press(win, Qt.Key.Key_Right)
    wait_state(qtbot, win, ShowState.PLAYING)
    press(win, Qt.Key.Key_Right)  # ignorée pendant la lecture
    assert win.controller.position == 0
    wait_state(qtbot, win, ShowState.HOLDING)
    assert win.surface.mode is SurfaceMode.STILL
    c = center_color(win)
    assert c.red() > 200 and c.green() < 40 and c.blue() < 40
    qtbot.wait(800)  # le maintien est indéfini : pas d'enchaînement automatique
    assert win.state is ShowState.HOLDING and win.controller.position == 0
    press(win, Qt.Key.Key_Right)
    wait_state(qtbot, win, ShowState.HOLDING)
    assert win.controller.position == 1
    assert win.surface.mode is SurfaceMode.BLACK
    press(win, Qt.Key.Key_Right)
    assert win.state is ShowState.FINISHED


def test_pause_resume_restart_and_blackout(qtbot, media):
    cue = Cue(name="A", video_path=str(media / "clip_audio.mp4"), end_behavior=EndBehavior.LAST_FRAME)
    win = make_window(qtbot, [cue])
    press(win, Qt.Key.Key_Right)
    wait_state(qtbot, win, ShowState.PLAYING)
    press(win, Qt.Key.Key_Space)
    assert win.state is ShowState.PAUSED
    qtbot.wait(1500)  # pause prolongée (plus longue que la vidéo)
    assert win.state is ShowState.PAUSED
    press(win, Qt.Key.Key_B)
    assert win.state is ShowState.BLACKOUT and win.surface.blackout
    c = center_color(win)
    assert (c.red(), c.green(), c.blue()) == (0, 0, 0)
    press(win, Qt.Key.Key_B)
    assert win.state is ShowState.PAUSED and not win.surface.blackout
    press(win, Qt.Key.Key_Space)
    assert win.state is ShowState.PLAYING
    press(win, Qt.Key.Key_R)
    assert win.state is ShowState.LOADING
    wait_state(qtbot, win, ShowState.PLAYING)
    wait_state(qtbot, win, ShowState.HOLDING)
    # « Dernière image vidéo » : l'image figée n'est pas noire
    assert win.surface.mode is SurfaceMode.STILL
    assert center_color(win) != QColor(0, 0, 0)


def test_unreadable_and_missing_videos_never_crash(qtbot, media):
    cues = [
        Cue(name="Corrompue", video_path=str(media / "corrupt.mp4"), image_path=str(media / "final_red.png")),
        Cue(name="Absente", video_path=str(media / "absente.mp4"), end_behavior=EndBehavior.BLACK),
        Cue(name="OK", video_path=str(media / "clip_silent.mp4"), image_path=str(media / "final_portrait_green.jpg")),
    ]
    win = make_window(qtbot, cues)
    press(win, Qt.Key.Key_Right)
    wait_state(qtbot, win, ShowState.ERROR)
    assert win.surface.mode is SurfaceMode.STILL  # repli sur l'image finale
    press(win, Qt.Key.Key_Right)
    wait_state(qtbot, win, ShowState.ERROR)
    assert win.surface.mode is SurfaceMode.BLACK
    press(win, Qt.Key.Key_Right)
    wait_state(qtbot, win, ShowState.HOLDING)
    # image portrait : proportions conservées, bandes noires sur les côtés
    image: QImage = win.surface.grab().toImage()
    assert QColor(image.pixel(2, image.height() // 2)) == QColor(0, 0, 0)
    assert QColor(image.pixel(image.width() // 2, image.height() // 2)).green() > 200


def test_exit_requires_double_shortcut_and_close_is_refused(qtbot, media):
    win = make_window(qtbot, [Cue(name="A", video_path=str(media / "clip_silent.mp4"))])
    win.close()  # Alt+F4 / fermeture système
    assert win.isVisible()
    with qtbot.waitSignal(win.exited, timeout=2000):
        ctrl_shift = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        press(win, Qt.Key.Key_Q, ctrl_shift)
        assert win.isVisible()
        press(win, Qt.Key.Key_Q, ctrl_shift)


def test_show_can_run_several_times(qtbot, media):
    for _ in range(3):
        win = make_window(qtbot, [Cue(name="A", video_path=str(media / "clip_silent.mp4"),
                                      image_path=str(media / "final_red.png"))])
        press(win, Qt.Key.Key_Right)
        wait_state(qtbot, win, ShowState.HOLDING)
        win.leave()


def test_transitions_never_paint_black_in_between(qtbot, media):
    """Vidéo → image finale → vidéo suivante : aucun rafraîchissement noir intermédiaire."""
    cues = [
        Cue(name="A", video_path=str(media / "clip_audio.mp4"), image_path=str(media / "final_red.png")),
        Cue(name="B", video_path=str(media / "clip_silent.mp4"), image_path=str(media / "final_red.png")),
    ]
    win = make_window(qtbot, cues)
    painted = []
    original = win.surface.paintEvent

    def spy(event):
        painted.append(win.surface.mode)
        original(event)

    win.surface.paintEvent = spy
    press(win, Qt.Key.Key_Right)
    wait_state(qtbot, win, ShowState.PLAYING)
    qtbot.waitUntil(lambda: SurfaceMode.VIDEO in painted, timeout=TIMEOUT)
    painted.clear()
    wait_state(qtbot, win, ShowState.HOLDING)
    press(win, Qt.Key.Key_Right)
    wait_state(qtbot, win, ShowState.HOLDING)
    qtbot.wait(50)
    sequence = [m for i, m in enumerate(painted) if i == 0 or painted[i - 1] is not m]
    assert sequence == [SurfaceMode.VIDEO, SurfaceMode.STILL, SurfaceMode.VIDEO, SurfaceMode.STILL]

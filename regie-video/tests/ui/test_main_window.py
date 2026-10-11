"""Tests de l'interface de préparation (affichage « offscreen »)."""

import shutil

import pytest
from PySide6.QtCore import Qt

from app.core.cue_state import ShowState
from app.models import EndBehavior
from app.persistence.app_settings import AppSettings
from app.ui import dialogs
from app.ui.main_window import MainWindow

pytestmark = pytest.mark.media


@pytest.fixture
def media(fixtures_dir, tmp_path):
    d = tmp_path / "medias"
    d.mkdir()
    for i in range(12):
        shutil.copy(fixtures_dir / "clip_silent.mp4", d / f"{i + 1:02d}_artiste-{i + 1}.mp4")
        shutil.copy(fixtures_dir / "final_red.png", d / f"{i + 1:02d}_artiste-{i + 1}.png")
    return d


@pytest.fixture
def window(qtbot):
    from app.ui.theme.stylesheet import apply_theme
    from PySide6.QtWidgets import QApplication

    apply_theme(QApplication.instance())
    w = MainWindow(AppSettings(repeat_interval_ms=100))
    w.show()
    yield w
    w.dirty = False  # pas de question à la fermeture
    w.close()
    w.deleteLater()


def test_empty_state_and_launch_disabled(window):
    assert window.list_stack.currentIndex() == 0
    assert not window.launch_btn.isEnabled()
    assert "0 séquence" in window.st_count.text()


def test_add_reorder_save_and_reopen(window, media, tmp_path, qtbot):
    paths = sorted(str(p) for p in media.glob("*.mp4"))
    window._add_paths(paths)
    assert len(window.show_model.cues) == 12
    assert all(c.image_path for c in window.show_model.cues)  # images associées par le nom
    assert window.dirty and window.launch_btn.isEnabled()
    first = window.show_model.cues[0]
    window._move_cue(0, 4)
    assert window.show_model.cues[4] is first
    qtbot.waitUntil(lambda: all(c.duration_ms for c in window.show_model.cues), timeout=30000)
    assert window.cue_model.status(first.id).text == "Prête"
    project = tmp_path / "gala.regievideo"
    assert window._save_to(str(project))
    assert not window.dirty
    order = [c.id for c in window.show_model.cues]

    other = MainWindow(AppSettings())
    qtbot.addWidget(other)
    assert other.open_show(str(project))
    assert [c.id for c in other.show_model.cues] == order
    assert other.show_model.cues[4].name == first.name


def test_delete_requires_confirmation(window, media, monkeypatch):
    window._add_paths(sorted(str(p) for p in media.glob("*.mp4"))[:3])
    window.cue_view.setCurrentIndex(window.cue_model.index(1))
    monkeypatch.setattr(dialogs, "confirm", lambda *a, **k: False)
    window.delete_selected()
    assert len(window.show_model.cues) == 3
    monkeypatch.setattr(dialogs, "confirm", lambda *a, **k: True)
    window.delete_selected()
    assert len(window.show_model.cues) == 2
    assert all(p.exists() for p in media.glob("*.mp4"))  # aucun fichier supprimé du disque


def test_duplicate_and_edit_properties(window, media):
    window._add_paths([str(sorted(media.glob("*.mp4"))[0])])
    window.duplicate_selected()
    assert len(window.show_model.cues) == 2
    cue = window.selected_cue()
    window._on_cue_edited(cue.id, {"end_behavior": EndBehavior.BLACK, "volume": 40})
    assert cue.end_behavior is EndBehavior.BLACK and cue.volume == 40
    window._on_cue_renamed(cue.id, "Nouveau nom")
    assert cue.name == "Nouveau nom"


def test_missing_media_is_reported(window, media, tmp_path):
    window._add_paths([str(p) for p in sorted(media.glob("*.mp4"))[:2]])
    (media / "01_artiste-1.mp4").unlink()
    window.refresh_statuses()
    assert window.cue_model.status(window.show_model.cues[0].id).text == "Vidéo manquante"
    assert "manquant" in window.st_missing.text()


def test_launch_and_exit_show_mode(window, media, qtbot, monkeypatch):
    window._add_paths([str(p) for p in sorted(media.glob("*.mp4"))[:2]])
    monkeypatch.setattr(dialogs, "launch_check", lambda *a: True)
    window.launch_show()
    projection = window._projection
    assert projection is not None and not window.isVisible()
    assert projection.state is ShowState.IDLE
    assert projection.cursor().shape() == Qt.CursorShape.BlankCursor
    projection.dispatch(projection.keyboard.bindings["Right"])
    qtbot.waitUntil(lambda: projection.state is ShowState.HOLDING, timeout=15000)
    projection.exit_guard.confirm = False
    from app.core.keyboard_controller import ShowAction
    projection.dispatch(ShowAction.EXIT)
    assert window._projection is None and window.isVisible()


def test_launch_cancelled_on_missing_files(window, media, monkeypatch):
    window._add_paths([str(sorted(media.glob("*.mp4"))[0])])
    (media / "01_artiste-1.mp4").unlink()
    seen = []
    monkeypatch.setattr(dialogs, "launch_check", lambda parent, issues: seen.append(issues) or False)
    window.launch_show()
    assert seen and window._projection is None


def test_media_information_panel_shows_real_values(window, fixtures_dir, qtbot):
    from app.media.media_info import find_ffprobe

    window._add_paths([str(fixtures_dir / "media" / "res_3289x1480_444.mp4")])
    cue = window.show_model.cues[0]
    qtbot.waitUntil(lambda: window.thumbs.result_for(cue.video_path) is not None, timeout=30000)
    if find_ffprobe():
        qtbot.waitUntil(lambda: window.analyzer.result_for(cue.video_path) is not None, timeout=30000)
    window._show_in_editor(cue)
    panel = window.editor.media_panel
    assert panel.video._values["Résolution"].text().startswith("3289 × 1480")
    assert panel.video._values["Format"].text() == "2,22:1"
    assert panel.verdict.text() != "Analyse…"
    status = window.cue_model.status(cue.id)
    assert status.detail == "3289 × 1480"


def test_diagnostic_dialog_with_real_playback_test(window, fixtures_dir, qtbot):
    from app.media.diagnostic import Overall
    from app.ui.diagnostic_dialog import DiagnosticDialog

    window._add_paths([str(fixtures_dir / "media" / "fps_25.mp4"), str(fixtures_dir / "media" / "audio_stereo_48k.mp4")])
    dlg = DiagnosticDialog(window, window)
    dlg.play_test.setChecked(True)
    dlg.passes.setValue(2)
    dlg.run()
    qtbot.waitUntil(lambda: dlg._report is not None, timeout=60000)
    report = dlg._report
    assert report.playback_tested
    assert all(len(runs) == 2 for runs in dlg._playback.values())
    assert report.overall in (Overall.READY, Overall.CHECK, Overall.BLOCKING)
    text = report.to_text("Test")
    assert "Lecture réelle" in text and "Projection" in text
    assert window._projection is None  # aucun passage en projection
    dlg.reject()

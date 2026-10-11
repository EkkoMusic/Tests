"""Point d'entrée de Régie Vidéo.

Usage :
    python main.py [spectacle.regievideo]
    python main.py --self-test      (vérifie le moteur vidéo, puis quitte)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from app import APP_ID, APP_NAME, ORGANIZATION, PROJECT_EXTENSION, __version__
from app.utils.logging import install_qt_message_handler, setup_logging
from app.utils.paths import logs_dir, resource_path


def _set_windows_app_id() -> None:
    """Icône correcte dans la barre des tâches Windows."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_ID}.{__version__}")
        except Exception:
            pass


def create_application(argv: list[str]):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication

    from app.ui.theme.stylesheet import apply_theme

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(resource_path("icons", "regie-video.ico"))))
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Dark)  # barres de titre sombres sous Windows 10/11
    apply_theme(app)
    return app


def run_self_test() -> int:
    """Vérifie la distribution : moteur vidéo, rendu GPU, analyse FFprobe.

    Lit la vidéo de test embarquée jusqu'à l'événement de fin de média,
    affiche une image dans la surface Qt Quick et analyse la vidéo avec
    FFprobe. Utilisé par la CI après compilation (bibliothèques Qt, FFmpeg,
    modules QML et FFprobe bien présents dans le dossier livré).
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtMultimedia import QMediaFormat
    from PySide6.QtWidgets import QApplication

    from app.media.media_info import ffprobe_version, find_ffprobe, probe_file
    from app.media.playback_engine import QtPlaybackEngine

    app = QApplication.instance() or create_application(sys.argv[:1])
    video = str(resource_path("selftest", "selftest.mp4"))
    engine = QtPlaybackEngine(with_audio=False)
    result = {"started": False, "ended": False, "frames": 0, "error": ""}
    engine.started.connect(lambda _t: result.update(started=True))
    engine.frameReady.connect(lambda _f: result.update(frames=result["frames"] + 1))
    engine.failed.connect(lambda _t, m: (result.update(error=m), app.quit()))
    engine.ended.connect(lambda _t: (result.update(ended=True), app.quit()))
    engine.load(video, 1)
    engine.play()
    QTimer.singleShot(20_000, app.quit)
    app.exec()
    codecs = [c.name for c in QMediaFormat().supportedVideoCodecs(QMediaFormat.ConversionMode.Decode)]
    video_ok = result["started"] and result["ended"] and result["frames"] > 0 and not result["error"]

    # Rendu accéléré (Qt Quick) : la scène doit afficher une image de test.
    gpu_ok, gpu_detail = False, ""
    try:
        from app.ui.widgets.quick_surface import QuickVideoSurface

        surface = QuickVideoSurface()
        surface.resize(160, 90)
        surface.show()
        img = QImage(16, 9, QImage.Format.Format_RGB32)
        img.fill(QColor(255, 0, 0))
        surface.show_still(img)
        grab = surface.grab_image()
        color = grab.pixelColor(80, 45) if not grab.isNull() else QColor()
        gpu_ok = color.red() > 200 and color.green() < 60
        gpu_detail = f"API {surface.graphics_api()}, pixel central {color.name()}"
        surface.close()
    except Exception as exc:
        gpu_detail = f"échec : {exc}"

    tool = find_ffprobe()
    probe_ok, probe_detail = False, "FFprobe introuvable"
    if tool:
        info = probe_file(video, tool)
        probe_ok = info.ok and info.video is not None and info.video.coded_width == 320
        probe_detail = f"{ffprobe_version(tool)} — {info.error or 'analyse correcte'}"
    require_probe = getattr(sys, "frozen", False)
    ok = video_ok and gpu_ok and (probe_ok or not require_probe)
    report = (f"{APP_NAME} {__version__} — auto-test {'RÉUSSI' if ok else 'ÉCHOUÉ'}\n"
              f"lecture : images décodées {result['frames']}, fin détectée {result['ended']}, "
              f"erreur {result['error'] or 'aucune'}\n"
              f"rendu accéléré : {'OK' if gpu_ok else 'ÉCHEC'} ({gpu_detail})\n"
              f"analyse FFprobe : {'OK' if probe_ok else 'ÉCHEC'} ({probe_detail})\n"
              f"décodeurs vidéo : {', '.join(codecs)}\n")
    (logs_dir() / "selftest.txt").write_text(report, encoding="utf-8")
    logging.getLogger("selftest").info(report)
    if sys.stdout is not None:
        print(report)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    log_file = setup_logging(logs_dir())
    log = logging.getLogger("regie_video")
    log.info("Démarrage de %s %s (journal : %s)", APP_NAME, __version__, log_file)
    _set_windows_app_id()

    if "--self-test" in argv:
        return run_self_test()

    app = create_application(argv)
    install_qt_message_handler()

    from app.ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    project = next((a for a in argv[1:] if a.lower().endswith(PROJECT_EXTENSION) and Path(a).is_file()), None)
    if not window.check_recovery():
        if project:
            window.open_show(os.path.abspath(project))
        else:
            window.reopen_last()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

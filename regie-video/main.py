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
    """Lit la vidéo de test embarquée et vérifie l'événement de fin de média.

    Utilisé après compilation pour vérifier que les bibliothèques
    multimédias (plugin FFmpeg de Qt) sont bien présentes dans la distribution.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtMultimedia import QMediaFormat
    from PySide6.QtWidgets import QApplication

    from app.media.playback_engine import QtPlaybackEngine

    app = QApplication.instance() or create_application(sys.argv[:1])
    engine = QtPlaybackEngine(with_audio=False)
    result = {"started": False, "ended": False, "frames": 0, "error": ""}
    engine.started.connect(lambda _t: result.update(started=True))
    engine.frameReady.connect(lambda _f: result.update(frames=result["frames"] + 1))
    engine.failed.connect(lambda _t, m: (result.update(error=m), app.quit()))
    engine.ended.connect(lambda _t: (result.update(ended=True), app.quit()))
    engine.load(str(resource_path("selftest", "selftest.mp4")), 1)
    engine.play()
    QTimer.singleShot(20_000, app.quit)
    app.exec()
    codecs = [c.name for c in QMediaFormat().supportedVideoCodecs(QMediaFormat.ConversionMode.Decode)]
    ok = result["started"] and result["ended"] and result["frames"] > 0 and not result["error"]
    report = (f"{APP_NAME} {__version__} — auto-test {'RÉUSSI' if ok else 'ÉCHOUÉ'}\n"
              f"images décodées : {result['frames']}, fin détectée : {result['ended']}, erreur : {result['error'] or 'aucune'}\n"
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

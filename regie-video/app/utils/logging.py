"""Journalisation technique locale. Rien n'est jamais affiché au public."""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s : %(message)s"


def setup_logging(log_dir: Path, level: int = logging.INFO) -> Path:
    log_file = log_dir / "regie-video.log"
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(file_handler)
    if sys.stderr is not None:  # absent dans l'exécutable fenêtré
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(console)

    def excepthook(exc_type, exc, tb):
        logging.getLogger("regie_video").critical("Exception non gérée", exc_info=(exc_type, exc, tb))

    sys.excepthook = excepthook
    threading.excepthook = lambda args: excepthook(args.exc_type, args.exc_value, args.exc_traceback)
    return log_file


def install_qt_message_handler() -> None:
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    qt_log = logging.getLogger("qt")
    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handler(mode, context, message):
        qt_log.log(levels.get(mode, logging.INFO), "%s", message)

    qInstallMessageHandler(handler)

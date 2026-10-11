"""Emplacements de l'application (données utilisateur, ressources, journaux)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app import APP_ID


def app_root() -> Path:
    """Racine des ressources : dossier du projet, ou dossier extrait par PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return app_root().joinpath("assets", *parts)


def user_data_dir() -> Path:
    """%APPDATA%\\RegieVideo sous Windows, ~/.local/share/RegieVideo ailleurs.

    La variable REGIE_VIDEO_DATA_DIR permet de l'isoler (tests).
    """
    override = os.environ.get("REGIE_VIDEO_DATA_DIR")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_ID
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_ID
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_ID
    base.mkdir(parents=True, exist_ok=True)
    return base


def logs_dir() -> Path:
    d = user_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def autosave_dir() -> Path:
    d = user_data_dir() / "autosave"
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_file() -> Path:
    return user_data_dir() / "settings.json"

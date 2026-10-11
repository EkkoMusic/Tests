"""Autosauvegarde de secours et récupération après incident.

Une copie de la conduite est écrite régulièrement dans le dossier de données
de l'application (jamais à côté du fichier projet, pour ne pas l'écraser).
Elle est supprimée lors d'un enregistrement ou d'une fermeture normale ; si
elle subsiste au démarrage suivant, c'est qu'un incident a eu lieu.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.models import Show

from .project_repository import show_from_dict, show_to_dict, write_json_atomic

log = logging.getLogger(__name__)

SUFFIX = ".autosave.json"


@dataclass
class RecoveryEntry:
    file: Path
    project_path: str | None
    show_name: str
    saved_at: datetime
    cue_count: int


class AutosaveStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _file_for(self, session_key: str) -> Path:
        digest = hashlib.sha1(session_key.encode("utf-8")).hexdigest()[:16]
        return self.directory / f"{digest}{SUFFIX}"

    def write(self, session_key: str, show: Show, project_path: str | None) -> Path:
        target = self._file_for(session_key)
        payload = {
            "project_path": project_path,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "show": show_to_dict(show, None),  # chemins absolus
        }
        write_json_atomic(target, payload)
        return target

    def discard(self, session_key: str) -> None:
        try:
            self._file_for(session_key).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            log.warning("Autosauvegarde impossible à supprimer", exc_info=True)

    def entries(self) -> list[RecoveryEntry]:
        found: list[RecoveryEntry] = []
        for file in sorted(self.directory.glob(f"*{SUFFIX}")):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                show = data["show"]
                found.append(
                    RecoveryEntry(
                        file=file,
                        project_path=data.get("project_path"),
                        show_name=str(show.get("name") or "Spectacle sans nom"),
                        saved_at=datetime.fromisoformat(data["saved_at"]),
                        cue_count=len(show.get("cues") or []),
                    )
                )
            except Exception:
                log.warning("Autosauvegarde illisible ignorée : %s", file, exc_info=True)
        found.sort(key=lambda e: e.saved_at, reverse=True)
        return found

    @staticmethod
    def load(entry: RecoveryEntry) -> Show:
        data = json.loads(entry.file.read_text(encoding="utf-8"))
        return show_from_dict(data["show"], None)

    @staticmethod
    def remove(entry: RecoveryEntry) -> None:
        try:
            entry.file.unlink()
        except OSError:
            pass

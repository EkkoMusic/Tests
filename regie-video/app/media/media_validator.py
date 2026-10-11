"""Vérification de la conduite avant le spectacle.

Contrôles rapides et sans moteur vidéo : présence, lisibilité, extension.
Les problèmes de décodage détectés par le service de miniatures (codec non
pris en charge, fichier corrompu) sont ajoutés via ``probe_errors``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.models import Cue, EndBehavior, Show

from .formats import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS


class Severity(str, Enum):
    ERROR = "error"      # la vidéo ne pourra pas être jouée
    WARNING = "warning"  # le spectacle fonctionnera, avec un repli (noir)


class FileStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    UNSUPPORTED = "unsupported"


@dataclass
class Issue:
    severity: Severity
    message: str
    cue_index: int | None = None
    cue_id: str | None = None


def check_file(path: str, extensions: tuple[str, ...]) -> FileStatus:
    if not path:
        return FileStatus.EMPTY
    p = Path(path)
    if not p.is_file():
        return FileStatus.MISSING
    if not os.access(p, os.R_OK):
        return FileStatus.UNREADABLE
    try:
        if p.stat().st_size == 0:
            return FileStatus.UNREADABLE
    except OSError:
        return FileStatus.UNREADABLE
    if p.suffix.lower() not in extensions:
        return FileStatus.UNSUPPORTED
    return FileStatus.OK


def video_status(cue: Cue) -> FileStatus:
    return check_file(cue.video_path, VIDEO_EXTENSIONS)


def image_status(path: str) -> FileStatus:
    return check_file(path, IMAGE_EXTENSIONS)


def cue_is_valid(cue: Cue) -> bool:
    if video_status(cue) is not FileStatus.OK:
        return False
    if cue.end_behavior is EndBehavior.IMAGE and cue.image_path:
        return image_status(cue.image_path) is FileStatus.OK
    return True


_VIDEO_MESSAGES = {
    FileStatus.EMPTY: "aucune vidéo choisie",
    FileStatus.MISSING: "vidéo introuvable",
    FileStatus.UNREADABLE: "vidéo illisible (accès refusé ou fichier vide)",
    FileStatus.UNSUPPORTED: "format vidéo non pris en charge",
}
_IMAGE_MESSAGES = {
    FileStatus.MISSING: "image finale introuvable — du noir sera affiché",
    FileStatus.UNREADABLE: "image finale illisible — du noir sera affiché",
    FileStatus.UNSUPPORTED: "format d'image non pris en charge — du noir sera affiché",
}


def validate_show(show: Show, probe_errors: dict[str, str] | None = None) -> list[Issue]:
    issues: list[Issue] = []
    if not show.cues:
        issues.append(Issue(Severity.ERROR, "La conduite ne contient aucune séquence."))
    probe_errors = probe_errors or {}
    for i, cue in enumerate(show.cues):
        label = f"{i + 1:02d} · {cue.name}"
        status = video_status(cue)
        if status is not FileStatus.OK:
            issues.append(Issue(Severity.ERROR, f"{label} : {_VIDEO_MESSAGES[status]}", i, cue.id))
        elif cue.video_path in probe_errors:
            issues.append(Issue(Severity.ERROR, f"{label} : {probe_errors[cue.video_path]}", i, cue.id))
        if cue.end_behavior is EndBehavior.IMAGE:
            if not cue.image_path:
                issues.append(Issue(Severity.WARNING, f"{label} : aucune image finale — du noir sera affiché", i, cue.id))
            else:
                img = image_status(cue.image_path)
                if img is not FileStatus.OK:
                    issues.append(Issue(Severity.WARNING, f"{label} : {_IMAGE_MESSAGES[img]}", i, cue.id))
    standby = show.settings.standby_image_path
    if standby and image_status(standby) is not FileStatus.OK:
        issues.append(Issue(Severity.WARNING, "Image d'attente introuvable — du noir sera affiché"))
    return issues


def missing_file_count(show: Show) -> int:
    count = 0
    for cue in show.cues:
        if cue.video_path and video_status(cue) is FileStatus.MISSING:
            count += 1
        if cue.end_behavior is EndBehavior.IMAGE and cue.image_path and image_status(cue.image_path) is FileStatus.MISSING:
            count += 1
    return count

"""Lecture et écriture des fichiers de spectacle ``.regievideo``.

Format : JSON UTF-8 versionné. Les chemins de médias situés dans le dossier du
projet (ou un sous-dossier) sont enregistrés en relatif, pour que le dossier
reste transportable ; les autres restent absolus. Aucun média n'est jamais
copié, déplacé ni supprimé.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from app import __version__
from app.models import Cue, EndBehavior, EndOfShowBehavior, Show, ShowSettings
from app.models.show import now_utc

log = logging.getLogger(__name__)

FORMAT_ID = "regie-video-show"
FORMAT_VERSION = 1


class ProjectError(Exception):
    """Erreur de projet, avec un message destiné à l'utilisateur (en français)."""


# ------------------------------------------------------------------- chemins
def encode_path(path: str, base_dir: Path | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if base_dir is not None and p.is_absolute():
        try:
            rel = p.resolve().relative_to(base_dir.resolve())
            return PurePosixPath(*rel.parts).as_posix()
        except ValueError:
            pass
    return str(p)


def decode_path(value: str, base_dir: Path | None) -> str:
    if not value:
        return ""
    if _looks_absolute(value):
        return os.path.normpath(value)
    relative = value.replace("\\", "/")  # les chemins relatifs sont écrits avec « / »
    return os.path.normpath(str(base_dir / relative) if base_dir is not None else relative)


def _looks_absolute(value: str) -> bool:
    # « C:\... » ou « \\serveur\... » doivent rester absolus, même lus hors Windows.
    return Path(value).is_absolute() or (len(value) > 2 and value[1] == ":") or value.startswith("\\\\")


# ------------------------------------------------------------- sérialisation
def show_to_dict(show: Show, base_dir: Path | None) -> dict[str, Any]:
    return {
        "format": FORMAT_ID,
        "format_version": FORMAT_VERSION,
        "app_version": __version__,
        "name": show.name,
        "created_at": show.created_at.isoformat(),
        "modified_at": show.modified_at.isoformat(),
        "settings": {
            "standby_image": encode_path(show.settings.standby_image_path, base_dir),
            "end_of_show": show.settings.end_of_show.value,
        },
        "cues": [
            {
                "id": c.id,
                "name": c.name,
                "video": encode_path(c.video_path, base_dir),
                "end_behavior": c.end_behavior.value,
                "image": encode_path(c.image_path, base_dir),
                "volume": c.volume,
                "duration_ms": c.duration_ms,
            }
            for c in show.cues
        ],
    }


def _parse_date(value: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return now_utc()


def show_from_dict(data: Any, base_dir: Path | None) -> Show:
    if not isinstance(data, dict) or data.get("format") != FORMAT_ID:
        raise ProjectError("Ce fichier n'est pas un spectacle Régie Vidéo.")
    version = data.get("format_version")
    if not isinstance(version, int) or version < 1:
        raise ProjectError("La version du fichier de spectacle est invalide.")
    if version > FORMAT_VERSION:
        raise ProjectError(
            "Ce spectacle a été créé avec une version plus récente de Régie Vidéo. "
            "Mettez le logiciel à jour pour l'ouvrir."
        )
    data = migrate(data)

    raw_settings = data.get("settings") or {}
    try:
        end_of_show = EndOfShowBehavior(raw_settings.get("end_of_show", "hold"))
    except ValueError:
        end_of_show = EndOfShowBehavior.HOLD
    settings = ShowSettings(
        standby_image_path=decode_path(str(raw_settings.get("standby_image") or ""), base_dir),
        end_of_show=end_of_show,
    )

    raw_cues = data.get("cues")
    if not isinstance(raw_cues, list):
        raise ProjectError("La conduite du spectacle est illisible (liste des séquences absente).")
    cues: list[Cue] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(raw_cues, start=1):
        if not isinstance(raw, dict):
            raise ProjectError(f"La séquence n° {i} est illisible.")
        try:
            behavior = EndBehavior(raw.get("end_behavior", "image"))
        except ValueError:
            behavior = EndBehavior.IMAGE
        duration = raw.get("duration_ms")
        cue = Cue(
            name=str(raw.get("name") or f"Séquence {i}"),
            video_path=decode_path(str(raw.get("video") or ""), base_dir),
            end_behavior=behavior,
            image_path=decode_path(str(raw.get("image") or ""), base_dir),
            volume=_safe_int(raw.get("volume"), 100),
            duration_ms=duration if isinstance(duration, int) and duration >= 0 else None,
        )
        cue_id = raw.get("id")
        if isinstance(cue_id, str) and cue_id and cue_id not in seen_ids:
            cue.id = cue_id
        seen_ids.add(cue.id)
        cues.append(cue)

    return Show(
        name=str(data.get("name") or "Spectacle sans nom"),
        cues=cues,
        settings=settings,
        created_at=_parse_date(data.get("created_at")),
        modified_at=_parse_date(data.get("modified_at")),
    )


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Point d'entrée des migrations de format (aucune pour la version 1)."""
    return data


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ fichiers
def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Écrit dans un fichier temporaire puis le substitue : jamais de fichier à moitié écrit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=path.suffix, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_show(show: Show, path: str | Path) -> Path:
    path = Path(path)
    show.modified_at = now_utc()
    payload = show_to_dict(show, path.parent)
    try:
        write_json_atomic(path, payload)
    except PermissionError as exc:
        raise ProjectError(f"Accès refusé : impossible d'écrire dans « {path.parent} ».") from exc
    except OSError as exc:
        raise ProjectError(f"Impossible d'enregistrer le spectacle : {exc.strerror or exc}.") from exc
    log.info("Spectacle enregistré : %s (%d séquences)", path, len(show.cues))
    return path


def load_show(path: str | Path) -> Show:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ProjectError(f"Le fichier « {path.name} » est introuvable.") from exc
    except PermissionError as exc:
        raise ProjectError(f"Accès refusé au fichier « {path.name} ».") from exc
    except UnicodeDecodeError as exc:
        raise ProjectError(f"« {path.name} » n'est pas un fichier de spectacle valide.") from exc
    except OSError as exc:
        raise ProjectError(f"Impossible de lire « {path.name} » : {exc.strerror or exc}.") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProjectError(
            f"« {path.name} » est endommagé (JSON invalide, ligne {exc.lineno}). "
            "Une autosauvegarde est peut-être disponible."
        ) from exc
    show = show_from_dict(data, path.parent)
    log.info("Spectacle ouvert : %s (%d séquences)", path, len(show.cues))
    return show

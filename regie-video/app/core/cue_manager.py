"""Opérations d'édition de la conduite (sans dépendance graphique)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

from app.media.formats import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from app.models import Cue, EndBehavior, Show


def name_from_file(path: str) -> str:
    """« 02_marie-dupont_final.mp4 » → « Marie Dupont Final »."""
    stem = Path(path).stem
    stem = re.sub(r"^\d+[\s._-]*", "", stem) or stem   # numéro d'ordre en tête
    stem = re.sub(r"[_.\-]+", " ", stem).strip()
    words = [w if any(c.isupper() for c in w[1:]) else w.capitalize() for w in stem.split()]
    return " ".join(words) or Path(path).stem


def find_matching_image(video_path: str) -> str:
    """Image portant le même nom que la vidéo, dans le même dossier."""
    video = Path(video_path)
    for ext in IMAGE_EXTENSIONS:
        for candidate in (video.with_suffix(ext), video.with_suffix(ext.upper())):
            if candidate.is_file():
                return str(candidate)
    return ""


class CueManager:
    """Modifie la liste des séquences d'un spectacle.

    Toutes les opérations retournent une valeur exploitable par l'interface
    et ne lèvent pas d'exception pour un identifiant inconnu.
    """

    def __init__(self, show: Show) -> None:
        self.show = show

    @property
    def cues(self) -> list[Cue]:
        return self.show.cues

    def add_videos(self, paths: Iterable[str], at: int | None = None) -> list[Cue]:
        created = []
        for path in paths:
            if Path(path).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            image = find_matching_image(path)
            created.append(
                Cue(
                    name=name_from_file(path),
                    video_path=os.path.normpath(path),
                    image_path=image,
                    end_behavior=EndBehavior.IMAGE if image else EndBehavior.BLACK,
                )
            )
        index = len(self.cues) if at is None else max(0, min(at, len(self.cues)))
        self.cues[index:index] = created
        return created

    def remove(self, cue_id: str) -> int:
        i = self.show.index_of(cue_id)
        if i >= 0:
            del self.cues[i]
        return i

    def duplicate(self, cue_id: str) -> Cue | None:
        i = self.show.index_of(cue_id)
        if i < 0:
            return None
        copy = self.cues[i].duplicate()
        self.cues.insert(i + 1, copy)
        return copy

    def move(self, source: int, destination: int) -> bool:
        """Déplace la séquence ``source`` pour qu'elle occupe l'index ``destination``."""
        n = len(self.cues)
        if not (0 <= source < n) or not (0 <= destination < n) or source == destination:
            return False
        cue = self.cues.pop(source)
        self.cues.insert(destination, cue)
        return True

    def rename(self, cue_id: str, name: str) -> bool:
        cue = self.show.cue_by_id(cue_id)
        name = name.strip()
        if cue is None or not name or cue.name == name:
            return False
        cue.name = name
        return True

    def relink_missing(self, folder: str) -> int:
        """Recherche dans ``folder`` (récursivement) les fichiers manquants, par nom.

        Retourne le nombre de chemins corrigés.
        """
        index: dict[str, str] = {}
        for root, _dirs, files in os.walk(folder):
            for f in files:
                index.setdefault(f.lower(), os.path.join(root, f))
        fixed = 0
        for cue in self.cues:
            for attr in ("video_path", "image_path"):
                current = getattr(cue, attr)
                if current and not os.path.isfile(current):
                    found = index.get(Path(current.replace("\\", "/")).name.lower())
                    if found:
                        setattr(cue, attr, os.path.normpath(found))
                        fixed += 1
        return fixed

"""Modèle d'un spectacle : métadonnées, réglages et conduite ordonnée."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .cue import Cue


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class EndOfShowBehavior(str, Enum):
    """Ce qu'affiche la projection quand on avance après la dernière séquence."""

    HOLD = "hold"        # garder l'affichage de la dernière séquence
    BLACK = "black"      # passer au noir
    STANDBY = "standby"  # revenir à l'image d'attente

    @property
    def label(self) -> str:
        return {
            EndOfShowBehavior.HOLD: "Garder la dernière image",
            EndOfShowBehavior.BLACK: "Passer au noir",
            EndOfShowBehavior.STANDBY: "Revenir à l'image d'attente",
        }[self]


@dataclass
class ShowSettings:
    """Réglages propres à un spectacle (enregistrés dans le fichier projet)."""

    standby_image_path: str = ""
    end_of_show: EndOfShowBehavior = EndOfShowBehavior.HOLD

    def __post_init__(self) -> None:
        if not isinstance(self.end_of_show, EndOfShowBehavior):
            self.end_of_show = EndOfShowBehavior(self.end_of_show)


@dataclass
class Show:
    name: str = "Nouveau spectacle"
    cues: list[Cue] = field(default_factory=list)
    settings: ShowSettings = field(default_factory=ShowSettings)
    created_at: datetime = field(default_factory=now_utc)
    modified_at: datetime = field(default_factory=now_utc)

    def index_of(self, cue_id: str) -> int:
        for i, cue in enumerate(self.cues):
            if cue.id == cue_id:
                return i
        return -1

    def cue_by_id(self, cue_id: str) -> Cue | None:
        i = self.index_of(cue_id)
        return self.cues[i] if i >= 0 else None

    def total_duration_ms(self) -> int:
        return sum(c.duration_ms or 0 for c in self.cues)

    def has_unknown_durations(self) -> bool:
        return any(c.duration_ms is None and c.video_path for c in self.cues)

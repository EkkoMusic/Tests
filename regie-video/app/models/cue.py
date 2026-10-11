"""Modèle d'une séquence (cue) de la conduite."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from enum import Enum


def new_cue_id() -> str:
    return uuid.uuid4().hex


class EndBehavior(str, Enum):
    """Ce que la projection affiche quand la vidéo d'une séquence se termine."""

    IMAGE = "image"            # image finale associée
    BLACK = "black"            # écran noir
    LAST_FRAME = "last_frame"  # maintien de la dernière image de la vidéo

    @property
    def label(self) -> str:
        return {
            EndBehavior.IMAGE: "Image finale",
            EndBehavior.BLACK: "Écran noir",
            EndBehavior.LAST_FRAME: "Dernière image vidéo",
        }[self]


@dataclass
class Cue:
    """Une séquence : une vidéo suivie d'un état de maintien.

    Les chemins sont toujours absolus en mémoire ; la conversion en chemins
    relatifs n'a lieu qu'à l'enregistrement du projet.
    """

    name: str
    video_path: str = ""
    end_behavior: EndBehavior = EndBehavior.IMAGE
    image_path: str = ""
    volume: int = 100
    duration_ms: int | None = None
    id: str = field(default_factory=new_cue_id)

    def __post_init__(self) -> None:
        self.volume = max(0, min(100, int(self.volume)))
        if not isinstance(self.end_behavior, EndBehavior):
            self.end_behavior = EndBehavior(self.end_behavior)

    @property
    def effective_end_behavior(self) -> EndBehavior:
        """Comportement réellement appliqué : sans image choisie, on passe au noir."""
        if self.end_behavior is EndBehavior.IMAGE and not self.image_path:
            return EndBehavior.BLACK
        return self.end_behavior

    def duplicate(self) -> "Cue":
        return replace(self, id=new_cue_id(), name=f"{self.name} (copie)")

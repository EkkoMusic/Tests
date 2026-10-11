"""Paramètres de l'application (communs à tous les spectacles)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any

from app.core.keyboard_controller import DEFAULT_BINDINGS

from .project_repository import write_json_atomic

log = logging.getLogger(__name__)

MAX_RECENT = 8


class FitMode(str, Enum):
    FIT = "fit"        # image entière, bandes noires si besoin
    FILL = "fill"      # remplit l'écran, rogne ce qui dépasse
    NATIVE = "native"  # un pixel du média = un pixel de l'écran, centré

    @property
    def label(self) -> str:
        return {
            FitMode.FIT: "Adapter à l'écran (recommandé)",
            FitMode.FILL: "Remplir l'écran (recadrage)",
            FitMode.NATIVE: "Taille native (1:1)",
        }[self]

    @property
    def consequence(self) -> str:
        return {
            FitMode.FIT: "Toute l'image est visible, sans déformation. Des bandes noires apparaissent "
                         "si le format du média diffère de celui de l'écran.",
            FitMode.FILL: "L'écran est entièrement rempli, sans déformation, mais les bords du média "
                          "qui dépassent sont coupés.",
            FitMode.NATIVE: "Aucune mise à l'échelle : un média plus petit que l'écran est entouré de noir, "
                            "un média plus grand est coupé. Utile seulement si le média est à la résolution exacte du projecteur.",
        }[self]


class Renderer(str, Enum):
    GPU = "gpu"  # Qt Quick, rendu par la carte graphique (recommandé)
    CPU = "cpu"  # rendu logiciel par le processeur (compatibilité)

    @property
    def label(self) -> str:
        return {Renderer.GPU: "Accéléré par la carte graphique (recommandé)",
                Renderer.CPU: "Compatibilité (processeur)"}[self]


@dataclass
class AppSettings:
    # Général
    reopen_last_project: bool = True
    recent_projects: list[str] = field(default_factory=list)
    # Projection
    fit_mode: str = FitMode.FIT.value
    renderer: str = Renderer.GPU.value
    projection_screen: str = ""          # nom de l'écran ; vide = écran principal
    # Audio
    master_volume: int = 100
    audio_device_id: str = ""            # vide = sortie système par défaut
    preview_volume: int = 70
    # Sécurité
    confirm_exit: bool = True
    repeat_protection: bool = True
    repeat_interval_ms: int = 400
    warn_missing_media: bool = True
    # Clavier (fixe en V1, mais stocké pour la personnalisation future)
    key_bindings: dict[str, str] = field(
        default_factory=lambda: {k: a.value for k, a in DEFAULT_BINDINGS.items()}
    )

    @property
    def fit(self) -> FitMode:
        try:
            return FitMode(self.fit_mode)
        except ValueError:
            return FitMode.FIT

    @property
    def render_mode(self) -> Renderer:
        try:
            return Renderer(self.renderer)
        except ValueError:
            return Renderer.GPU

    @property
    def effective_repeat_interval_ms(self) -> int:
        return self.repeat_interval_ms if self.repeat_protection else 0

    def push_recent(self, path: str) -> None:
        normalized = str(Path(path))
        self.recent_projects = [p for p in self.recent_projects if p != normalized]
        self.recent_projects.insert(0, normalized)
        del self.recent_projects[MAX_RECENT:]

    def forget_recent(self, path: str) -> None:
        self.recent_projects = [p for p in self.recent_projects if p != str(Path(path))]

    # ---------------------------------------------------------- persistance
    @classmethod
    def load(cls, path: Path) -> "AppSettings":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except Exception:
            log.warning("Paramètres illisibles, valeurs par défaut utilisées", exc_info=True)
            return cls()
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Any) -> "AppSettings":
        settings = cls()
        if not isinstance(data, dict):
            return settings
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            default = getattr(settings, f.name)
            if isinstance(default, bool):
                if isinstance(value, bool):
                    setattr(settings, f.name, value)
            elif isinstance(default, int):
                if isinstance(value, int) and not isinstance(value, bool):
                    setattr(settings, f.name, value)
            elif isinstance(default, str):
                if isinstance(value, str):
                    setattr(settings, f.name, value)
            elif isinstance(default, list):
                if isinstance(value, list):
                    setattr(settings, f.name, [str(v) for v in value][:MAX_RECENT])
            elif isinstance(default, dict) and isinstance(value, dict):
                setattr(settings, f.name, {str(k): str(v) for k, v in value.items()})
        settings.master_volume = max(0, min(100, settings.master_volume))
        settings.preview_volume = max(0, min(100, settings.preview_volume))
        settings.repeat_interval_ms = max(100, min(3000, settings.repeat_interval_ms))
        return settings

    def save(self, path: Path) -> None:
        try:
            write_json_atomic(path, asdict(self))
        except OSError:
            log.exception("Impossible d'enregistrer les paramètres")

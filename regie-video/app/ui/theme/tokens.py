"""Design system de Régie Vidéo : couleurs, typographie, espacements, rayons.

Toutes les couleurs et dimensions de l'interface proviennent d'ici ; aucun
widget ne définit sa propre couleur en dur.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str = "#0E1117"            # fond principal bleu-noir
    surface: str = "#161B24"       # panneaux
    surface_2: str = "#1E2531"     # champs, cartes
    surface_3: str = "#283142"     # survol
    border: str = "#262E3B"        # séparateurs discrets
    border_strong: str = "#36404F"
    accent: str = "#738CFF"        # bleu électrique
    accent_hover: str = "#8CA0FF"
    accent_pressed: str = "#5C76F0"
    accent_soft: str = "rgba(115, 140, 255, 0.16)"
    accent_2: str = "#A07CFF"      # violet doux (dégradé du bouton « Lancer »)
    text: str = "#F3F5FA"
    text_2: str = "#9DA8BA"
    text_3: str = "#677287"
    on_accent: str = "#0B0E14"
    error: str = "#EF646A"
    error_soft: str = "rgba(239, 100, 106, 0.14)"
    success: str = "#55C89B"
    success_soft: str = "rgba(85, 200, 155, 0.14)"
    warning: str = "#F2B45A"
    warning_soft: str = "rgba(242, 180, 90, 0.14)"
    black: str = "#000000"


@dataclass(frozen=True)
class Typography:
    family: str = '"Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'
    display_family: str = '"Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI", "Inter", sans-serif'
    mono_family: str = '"Cascadia Mono", "Consolas", "JetBrains Mono", monospace'
    xs: int = 11
    sm: int = 12
    md: int = 13
    lg: int = 15
    xl: int = 18
    xxl: int = 22


@dataclass(frozen=True)
class Spacing:
    xxs: int = 2
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass(frozen=True)
class Radius:
    sm: int = 6
    md: int = 8
    lg: int = 12
    pill: int = 999


COLORS = Palette()
FONT = Typography()
SPACE = Spacing()
RADIUS = Radius()

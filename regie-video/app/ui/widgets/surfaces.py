"""Choix du moteur de rendu de la surface de projection."""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

from app.persistence.app_settings import Renderer

from .video_surface import VideoSurface

log = logging.getLogger(__name__)


def create_surface(renderer: Renderer, parent: QWidget | None = None):
    """Surface GPU si demandée et disponible, sinon repli explicite sur le rendu processeur.

    Le repli n'est jamais silencieux : il est journalisé et la surface
    retournée expose ``renderer_name`` (affiché dans le diagnostic).
    """
    if renderer is Renderer.GPU:
        try:
            from .quick_surface import QuickVideoSurface

            return QuickVideoSurface(parent)
        except Exception as exc:  # module QML absent, pilote graphique…
            log.error("Rendu GPU indisponible, repli sur le rendu processeur : %s", exc)
            surface = VideoSurface(parent)
            surface.fallback_reason = str(exc)
            return surface
    return VideoSurface(parent)

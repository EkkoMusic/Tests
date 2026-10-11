"""Empêche la mise en veille de l'écran pendant le spectacle (Windows).

Une image finale peut rester affichée de longues minutes : sans cette
précaution, Windows pourrait éteindre l'écran ou lancer l'économiseur.
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


def keep_display_awake(enabled: bool) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        flags = _ES_CONTINUOUS
        if enabled:
            flags |= _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
        ok = ctypes.windll.kernel32.SetThreadExecutionState(flags) != 0
        log.info("Veille de l'écran %s", "bloquée" if enabled else "rétablie")
        return ok
    except Exception:  # pragma: no cover - dépend du système
        log.exception("Impossible de modifier l'état de veille")
        return False

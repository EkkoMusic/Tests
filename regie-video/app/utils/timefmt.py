"""Formatage des durées en français."""

from __future__ import annotations


def format_clock(ms: int | None) -> str:
    """75 000 → « 01:15 » ; 3 723 000 → « 1:02:03 »."""
    if ms is None or ms < 0:
        return "--:--"
    total = int(ms // 1000)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_duration_long(ms: int) -> str:
    """Durée lisible : « 18 min 40 s », « 1 h 05 min », « 45 s »."""
    total = int(round(ms / 1000))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"

"""Mesures de lecture : délai de démarrage, régularité, images manquantes.

Ce qui est mesuré : les images que le moteur Qt Multimedia livre réellement à
l'application, avec leur horodatage. Une image que le décodeur n'a pas pu
fournir à temps est sautée par Qt : elle apparaît comme un « trou » dans les
horodatages. Ce qui n'est pas mesuré : la présentation finale par la carte
graphique et l'écran (synchronisation verticale), inaccessible depuis Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlaybackReport:
    frames: int = 0
    expected_frames: int | None = None
    missing_frames: int = 0
    startup_ms: float | None = None          # du lancement à la première image
    max_gap_ms: float = 0.0                  # plus long intervalle entre deux images reçues
    late_frames: int = 0                     # images reçues avec plus d'une période de retard
    realtime_ratio: float | None = None      # durée média lue / temps réel écoulé
    media_span_ms: float = 0.0
    wall_ms: float = 0.0
    gaps_ms: list[float] = field(default_factory=list, repr=False)

    @property
    def missing_ratio(self) -> float:
        total = self.frames + self.missing_frames
        return self.missing_frames / total if total else 0.0

    def summary_fr(self) -> str:
        parts = [f"{self.frames} images reçues"]
        if self.missing_frames:
            parts.append(f"{self.missing_frames} sautées ({self.missing_ratio:.1%})".replace(".", ","))
        else:
            parts.append("aucune image sautée")
        if self.startup_ms is not None:
            parts.append(f"démarrage {self.startup_ms:.0f} ms")
        parts.append(f"écart max {self.max_gap_ms:.0f} ms")
        if self.realtime_ratio is not None:
            parts.append(f"vitesse {self.realtime_ratio:.2f}×".replace(".", ","))
        return " · ".join(parts)


class FrameTelemetry:
    """Accumule les images reçues. Les temps sont en secondes (horloge
    monotone) et les horodatages des images en microsecondes."""

    def __init__(self, fps: float | None = None) -> None:
        self.fps = fps if fps and fps > 0 else None
        self.reset()

    def reset(self, launched_at: float | None = None) -> None:
        self._launched = launched_at
        self._first_arrival: float | None = None
        self._last_arrival: float | None = None
        self._first_pts: int | None = None
        self._last_pts: int | None = None
        self._report = PlaybackReport()
        self._paused_since_first = False

    @property
    def frame_period_us(self) -> float | None:
        return 1_000_000 / self.fps if self.fps else None

    def feed(self, arrival_s: float, pts_us: int) -> None:
        r = self._report
        r.frames += 1
        if self._first_arrival is None:
            self._first_arrival = arrival_s
            self._first_pts = pts_us
            if self._launched is not None:
                r.startup_ms = (arrival_s - self._launched) * 1000
        elif self._last_arrival is not None:
            gap = (arrival_s - self._last_arrival) * 1000
            r.gaps_ms.append(gap)
            r.max_gap_ms = max(r.max_gap_ms, gap)
            period = self.frame_period_us
            if period and pts_us >= 0 and self._last_pts is not None and self._last_pts >= 0:
                delta = pts_us - self._last_pts
                if delta > 1.5 * period:
                    r.missing_frames += int(round(delta / period)) - 1
                if gap > 2 * period / 1000:
                    r.late_frames += 1
        self._last_arrival = arrival_s
        if pts_us >= 0:
            self._last_pts = pts_us

    def interrupt(self) -> None:
        """Pause ou déplacement : l'intervalle suivant n'est pas une anomalie."""
        self._last_arrival = None
        self._last_pts = None
        self._paused_since_first = True

    def report(self) -> PlaybackReport:
        r = self._report
        if self._first_arrival is not None and self._last_arrival is not None:
            r.wall_ms = (self._last_arrival - self._first_arrival) * 1000
            if (not getattr(self, "_paused_since_first", False) and self._first_pts is not None
                    and self._last_pts is not None and self._last_pts > self._first_pts):
                r.media_span_ms = (self._last_pts - self._first_pts) / 1000
                if r.wall_ms > 0:
                    r.realtime_ratio = r.media_span_ms / r.wall_ms
            if self.fps:
                r.expected_frames = r.frames + r.missing_frames
        return r

"""Bilan du diagnostic « Vérifier la diffusion ».

Ce module ne fait qu'agréger des constats : il ne lit ni n'affiche aucun
média. La distinction est explicite entre ce qui est *détecté*
(compatibilité présumée d'après les caractéristiques) et ce qui est *mesuré*
(test de lecture réel).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app import APP_NAME, __version__
from app.models import EndBehavior, Show

from .compatibility import Assessment, Severity, Verdict
from .media_validator import FileStatus, image_status, video_status
from .system_info import SystemInfo
from .telemetry import PlaybackReport


class Overall(str, Enum):
    READY = "ready"
    CHECK = "check"
    BLOCKING = "blocking"

    @property
    def label(self) -> str:
        return {Overall.READY: "Prêt pour le spectacle",
                Overall.CHECK: "Vérification matérielle recommandée",
                Overall.BLOCKING: "Problèmes bloquants"}[self]

    @property
    def kind(self) -> str:
        return {Overall.READY: "success", Overall.CHECK: "warning", Overall.BLOCKING: "error"}[self]


class Level(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass
class DiagItem:
    category: str      # Médias, Projection, Audio, Système
    level: Level
    title: str
    detail: str = ""


@dataclass
class DiagnosticReport:
    items: list[DiagItem] = field(default_factory=list)
    overall: Overall = Overall.CHECK
    playback_tested: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def count(self, level: Level) -> int:
        return sum(1 for i in self.items if i.level is level)

    def to_text(self, show_name: str) -> str:
        lines = [f"{APP_NAME} {__version__} — Vérification de la diffusion",
                 f"Spectacle : {show_name}",
                 f"Date : {self.created_at.strftime('%d/%m/%Y %H:%M')}",
                 f"Bilan : {self.overall.label}",
                 f"Test de lecture réel : {'effectué' if self.playback_tested else 'non effectué'}", ""]
        marks = {Level.OK: "[OK]", Level.INFO: "[i]", Level.WARNING: "[!]", Level.BLOCKING: "[X]"}
        category = None
        for item in self.items:
            if item.category != category:
                category = item.category
                lines += ["", f"== {category} =="]
            lines.append(f"{marks[item.level]} {item.title}")
            if item.detail:
                lines += [f"     {d}" for d in item.detail.splitlines()]
        return "\n".join(lines) + "\n"


_SEV_TO_LEVEL = {Severity.BLOCKING: Level.BLOCKING, Severity.PERF: Level.WARNING,
                 Severity.WARNING: Level.WARNING, Severity.INFO: Level.INFO}


def build_report(
    show: Show,
    assessments: dict[str, Assessment],
    system: SystemInfo,
    renderer_name: str,
    renderer_fallback: str = "",
    playback: dict[str, list[PlaybackReport]] | None = None,
    media_has_audio: dict[str, bool] | None = None,
) -> DiagnosticReport:
    """``assessments`` et ``playback`` sont indexés par identifiant de séquence."""
    report = DiagnosticReport(playback_tested=bool(playback))
    add = report.items.append
    playback_items: list[DiagItem] = []
    cadence_notes: dict[str, Level] = {}
    media_has_audio = media_has_audio or {}

    # ---------------------------------------------------------------- médias
    if not show.cues:
        add(DiagItem("Médias", Level.BLOCKING, "La conduite ne contient aucune séquence."))
    for i, cue in enumerate(show.cues):
        name = f"{i + 1:02d} · {cue.name}"
        vs = video_status(cue)
        if vs is not FileStatus.OK:
            reason = {FileStatus.EMPTY: "aucune vidéo choisie", FileStatus.MISSING: "fichier introuvable",
                      FileStatus.UNREADABLE: "fichier illisible (accès refusé ou vide)",
                      FileStatus.UNSUPPORTED: "extension non prise en charge"}[vs]
            add(DiagItem("Médias", Level.BLOCKING, f"{name} : {reason}", cue.video_path))
            continue
        a = assessments.get(cue.id)
        if a is None:
            add(DiagItem("Médias", Level.WARNING, f"{name} : analyse non terminée"))
            continue
        level = {Verdict.VERIFIED: Level.OK, Verdict.PRESUMED: Level.WARNING, Verdict.PERF_RISK: Level.WARNING,
                 Verdict.UNSUPPORTED: Level.BLOCKING, Verdict.UNKNOWN: Level.WARNING}[a.verdict]
        details = [f.message for f in a.findings if f.affects_verdict
                   and (f.severity is not Severity.INFO or a.verdict is not Verdict.VERIFIED)]
        for f in a.findings:
            if not f.affects_verdict and f.message.startswith("Cadence"):
                cadence_notes[f.message] = Level.WARNING if f.severity is not Severity.INFO else Level.INFO
            elif not f.affects_verdict:
                details.append(f.message)
        add(DiagItem("Médias", level, f"{name} : {a.verdict.label}", "\n".join(details)))
        if cue.end_behavior is EndBehavior.IMAGE and cue.image_path and image_status(cue.image_path) is not FileStatus.OK:
            add(DiagItem("Médias", Level.WARNING, f"{name} : image finale introuvable — du noir sera affiché", cue.image_path))
        runs = (playback or {}).get(cue.id)
        if runs:
            worst = max(runs, key=lambda r: (r.frames == 0, r.missing_ratio, -(r.realtime_ratio or 1)))
            ok = worst.frames > 0 and worst.missing_ratio <= 0.01 and (worst.realtime_ratio or 1) >= 0.97
            playback_items.append(DiagItem("Lecture réelle", Level.OK if ok else Level.WARNING,
                         f"{name} : {len(runs)} passage(s) — {'fluide' if ok else 'irrégularités mesurées'}",
                         "\n".join(f"Passage {k + 1} : {r.summary_fr()}" for k, r in enumerate(runs))))

    report.items.extend(playback_items)

    # ------------------------------------------------------------ projection
    d = system.projection
    if d is None:
        add(DiagItem("Projection", Level.BLOCKING, "Aucun écran détecté."))
    else:
        add(DiagItem("Projection", Level.OK, f"Écran « {d.name} » : {d.describe()}"))
        if not d.refresh_hz:
            add(DiagItem("Projection", Level.INFO, "Fréquence de rafraîchissement non communiquée par Windows."))
        if len(system.displays) > 1:
            add(DiagItem("Projection", Level.INFO,
                         f"{len(system.displays)} écrans détectés (mode « Étendre ») : vérifiez l'écran choisi dans Paramètres → Projection."))
        else:
            add(DiagItem("Projection", Level.INFO,
                         "Un seul écran visible : en mode « Dupliquer », Windows impose une résolution commune "
                         "à l'écran du portable et au projecteur. Vérifiez qu'elle correspond à la résolution native du projecteur."))
    for message, level in cadence_notes.items():
        add(DiagItem("Projection", level, message))
    add(DiagItem("Projection", Level.OK if not renderer_fallback else Level.WARNING,
                 f"Rendu vidéo : {renderer_name}", renderer_fallback))

    # ----------------------------------------------------------------- audio
    any_audio = any(media_has_audio.values())
    if system.audio_output is None:
        add(DiagItem("Audio", Level.BLOCKING if any_audio else Level.WARNING, "Aucune sortie audio disponible",
                     "Branchez ou activez une sortie audio dans Windows." if any_audio else "Les médias analysés n'ont pas de son."))
    else:
        out = system.audio_output
        add(DiagItem("Audio", Level.OK, f"Sortie : {out.description}", out.describe()))
        if system.audio_selected_missing:
            add(DiagItem("Audio", Level.WARNING, "La sortie choisie dans les paramètres est absente : sortie par défaut utilisée."))
        add(DiagItem("Audio", Level.INFO, "Le fichier est lu sans réencodage ; Windows peut toutefois rééchantillonner "
                                          "ou mixer le son (mode partagé) : la sortie n'est pas garantie bit à bit."))

    # --------------------------------------------------------------- système
    if system.ffprobe_path:
        add(DiagItem("Système", Level.OK, f"Analyse des médias : FFprobe {system.ffprobe_version or ''}".strip()))
    else:
        add(DiagItem("Système", Level.WARNING, "FFprobe indisponible : analyse partielle des médias."))
    add(DiagItem("Système", Level.INFO, f"{system.os_name} · {system.cpu_count} cœurs logiques · {system.qt_version}"))

    # ------------------------------------------------------------------ bilan
    levels = {i.level for i in report.items}
    if Level.BLOCKING in levels:
        report.overall = Overall.BLOCKING
    elif Level.WARNING in levels or not report.playback_tested:
        report.overall = Overall.CHECK
        if not report.playback_tested:
            add(DiagItem("Système", Level.INFO, "Fluidité non mesurée : lancez le test de lecture réel pour la confirmer."))
    else:
        report.overall = Overall.READY
    return report

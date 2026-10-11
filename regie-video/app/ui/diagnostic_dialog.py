"""Fenêtre « Vérifier la diffusion » : diagnostic avant spectacle."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME
from app.media.diagnostic import DiagnosticReport, Level, build_report
from app.media.media_validator import FileStatus, video_status
from app.media.playback_tester import PlaybackJob, PlaybackTester

from .theme import icons
from .theme.tokens import COLORS, SPACE
from .widgets.common import Pill, Toggle, button, label, section_label

log = logging.getLogger(__name__)

ANALYSIS_TIMEOUT_MS = 120_000


class DiagnosticDialog(QDialog):
    def __init__(self, window, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.window_ = window
        self.setWindowTitle(f"Vérifier la diffusion — {APP_NAME}")
        self.setMinimumSize(760, 620)
        self._tester: PlaybackTester | None = None
        self._playback: dict[str, list] = {}
        self._report: DiagnosticReport | None = None
        self._wait_started = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.lg)
        root.setSpacing(SPACE.md)
        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.addWidget(label("Vérifier la diffusion", "display"))
        title_box.addWidget(label("Contrôle des médias, de l'écran de projection et de la sortie audio. "
                                  "Rien n'est affiché sur la projection ni diffusé sur les haut-parleurs.", "muted", wrap=True))
        head.addLayout(title_box, 1)
        self.overall = Pill("Non vérifié", "neutral")
        self.overall.setMinimumHeight(28)
        head.addWidget(self.overall, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)

        # Options du test de lecture réel
        opts = QHBoxLayout()
        opts.setSpacing(SPACE.sm)
        self.play_test = Toggle(False)
        opts.addWidget(self.play_test)
        opts.addWidget(label("Test de lecture réel de chaque vidéo", ""))
        opts.addSpacing(SPACE.md)
        opts.addWidget(label("Passages", "caption"))
        self.passes = QSpinBox()
        self.passes.setRange(1, 3)
        self.passes.setValue(2)
        opts.addWidget(self.passes)
        opts.addWidget(label("Durée", "caption"))
        self.span = QComboBox()
        self.span.addItem("10 s par passage", 10)
        self.span.addItem("30 s par passage", 30)
        self.span.addItem("Vidéo entière", 0)
        self.span.setCurrentIndex(0)
        opts.addWidget(self.span)
        opts.addStretch(1)
        root.addLayout(opts)
        root.addWidget(label("Le test décode réellement chaque vidéo en temps réel (son coupé, aucune image affichée) "
                             "et mesure les images sautées et la régularité. Il ne remplace pas une répétition "
                             "sur le vidéoprojecteur : le coût de l'affichage n'est pas inclus.", "caption", wrap=True))

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet(f"QProgressBar {{ background: {COLORS.surface_3}; border: none; border-radius: 3px; }}"
                                    f"QProgressBar::chunk {{ background: {COLORS.accent}; border-radius: 3px; }}")
        root.addWidget(self.progress)
        self.status = label("Cliquez sur « Lancer la vérification ».", "muted")
        root.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("Transparent")
        self.scroll.setWidgetResizable(True)
        self.results = QWidget()
        self.results.setObjectName("Transparent")
        self.results_layout = QVBoxLayout(self.results)
        self.results_layout.setContentsMargins(0, 0, SPACE.sm, 0)
        self.results_layout.setSpacing(SPACE.xs)
        self.results_layout.addStretch(1)
        self.scroll.setWidget(self.results)
        root.addWidget(self.scroll, 1)

        buttons = QHBoxLayout()
        self.save_btn = button("Enregistrer le rapport…", "save", "ghost")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_report)
        buttons.addWidget(self.save_btn)
        buttons.addStretch(1)
        self.close_btn = button("Fermer")
        self.close_btn.clicked.connect(self.reject)
        self.run_btn = button("Lancer la vérification", "shield", "primary")
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self.run)
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.run_btn)
        root.addLayout(buttons)

        self._poll = QTimer(self)
        self._poll.setInterval(200)
        self._poll.timeout.connect(self._wait_analysis)

    # ------------------------------------------------------------- déroulé
    def run(self) -> None:
        w = self.window_
        self.run_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self._playback = {}
        self._clear()
        w.refresh_system()
        for cue in w.show_model.cues:
            if video_status(cue) is FileStatus.OK:
                w.thumbs.request(cue.video_path)
                w.analyzer.request(cue.video_path)
        self.status.setText("Analyse des médias…")
        self.progress.setRange(0, 0)
        self._wait_started = 0
        self._poll.start()

    def _pending_analysis(self) -> int:
        w = self.window_
        n = 0
        for cue in w.show_model.cues:
            if video_status(cue) is not FileStatus.OK:
                continue
            if w.thumbs.result_for(cue.video_path) is None:
                n += 1
            elif w.analyzer.available and w.analyzer.result_for(cue.video_path) is None:
                n += 1
        return n

    def _wait_analysis(self) -> None:
        self._wait_started += self._poll.interval()
        pending = self._pending_analysis()
        total = len(self.window_.show_model.cues)
        self.status.setText(f"Analyse des médias… {total - pending}/{total}")
        if pending and self._wait_started < ANALYSIS_TIMEOUT_MS:
            return
        self._poll.stop()
        if self.play_test.isChecked():
            self._start_playback()
        else:
            self._finish()

    def _start_playback(self) -> None:
        w = self.window_
        jobs = [PlaybackJob(c.id, c.video_path, c.duration_ms) for c in w.show_model.cues
                if video_status(c) is FileStatus.OK and c.video_path not in w._probe_errors]
        if not jobs:
            self._finish()
            return
        span = self.span.currentData()
        self._tester = PlaybackTester(self.passes.value(), span or None, self)
        self._tester.progress.connect(self._on_progress)
        self._tester.measured.connect(lambda key, r: self._playback.setdefault(key, []).append(r))
        self._tester.finished.connect(self._finish)
        self.progress.setRange(0, len(jobs) * self.passes.value())
        self._tester.start(jobs)

    def _on_progress(self, step: int, total: int, what: str) -> None:
        key, n = what.split("|")
        cue = self.window_.show_model.cue_by_id(key)
        name = cue.name if cue else key
        self.progress.setValue(step)
        self.status.setText(f"Test de lecture : « {name} », passage {n} ({step + 1}/{total})")

    def _finish(self) -> None:
        w = self.window_
        assessments = {}
        has_audio = {}
        for cue in w.show_model.cues:
            if video_status(cue) is not FileStatus.OK:
                continue
            runs = self._playback.get(cue.id)
            worst = None
            if runs:
                worst = max(runs, key=lambda r: (r.frames == 0, r.missing_ratio))
            assessments[cue.id] = w.assess(cue, worst)
            info = w.media_info_for(cue)
            probe = w.thumbs.result_for(cue.video_path)
            has_audio[cue.id] = bool(info and info.audio) or bool(probe and probe.has_audio)
        surface = w.preview.surface
        self._report = build_report(
            w.show_model, assessments, w.system, surface.renderer_name,
            getattr(surface, "fallback_reason", ""), self._playback or None, has_audio)
        self._show_report(self._report)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.status.setText("Vérification terminée." if self._report.playback_tested
                            else "Vérification terminée (sans test de lecture réel).")
        self.run_btn.setEnabled(True)
        self.run_btn.setText("  Relancer")
        self.save_btn.setEnabled(True)
        log.info("Diagnostic : %s", self._report.overall.label)

    # ------------------------------------------------------------- rendu
    def _clear(self) -> None:
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_report(self, report: DiagnosticReport) -> None:
        self._clear()
        self.overall.set_kind(report.overall.kind, report.overall.label)
        category = None
        pos = 0
        for item in report.items:
            if item.category != category:
                category = item.category
                if pos:
                    self.results_layout.insertSpacing(pos, SPACE.md)
                    pos += 1
                self.results_layout.insertWidget(pos, section_label(category))
                pos += 1
            self.results_layout.insertWidget(pos, self._row(item))
            pos += 1

    def _row(self, item) -> QWidget:
        icon_name, color = {
            Level.OK: ("check-circle", COLORS.success), Level.INFO: ("info", COLORS.text_3),
            Level.WARNING: ("alert", COLORS.warning), Level.BLOCKING: ("x-circle", COLORS.error),
        }[item.level]
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(SPACE.sm)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, color, 16))
        lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(label(item.title, "", wrap=True))
        if item.detail:
            texts.addWidget(label(item.detail, "caption", wrap=True))
        lay.addLayout(texts, 1)
        return row

    def _save_report(self) -> None:
        if self._report is None:
            return
        w = self.window_
        start = Path(w.project_path).with_suffix(".diagnostic.txt") if w.project_path else Path.home() / "diagnostic.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le rapport", str(start), "Texte (*.txt)")
        if path:
            Path(path).write_text(self._report.to_text(w.show_model.name), encoding="utf-8")

    def reject(self) -> None:
        if self._tester is not None:
            self._tester.cancel()
            self._tester = None
        self._poll.stop()
        super().reject()

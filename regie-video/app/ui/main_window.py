"""Fenêtre principale du mode préparation."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QGuiApplication, QKeySequence
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, PROJECT_EXTENSION, PROJECT_FILTER, __version__
from app.media.formats import IMAGE_EXTENSIONS, VIDEO_FILTER
from app.media.image_loader import read_image
from app.media.media_validator import (
    FileStatus,
    Severity,
    image_status,
    missing_file_count,
    validate_show,
    video_status,
)
from app.media import system_info
from app.media.analyzer import MediaAnalyzer
from app.media.compatibility import Assessment, assess_media
from app.media.media_info import MediaInfo, fr_number, media_info_from_qt
from app.media.thumbnail_service import ProbeResult, ThumbnailService
from app.models import Cue, EndBehavior, Show
from app.persistence.app_settings import AppSettings
from app.persistence.autosave import AutosaveStore
from app.persistence.project_repository import ProjectError, load_show, save_show
from app.utils.paths import autosave_dir, settings_file
from app.utils.timefmt import format_duration_long

from . import dialogs
from .cue_editor import CueEditor
from .cue_list import CueDelegate, CueListModel, CueListView, CueStatus
from .preview_panel import PreviewPanel
from .projection_window import ProjectionWindow
from .settings_dialog import SettingsDialog
from .theme import icons
from .theme.tokens import COLORS, SPACE
from .widgets.common import EmptyState, Logo, Pill, Toast, button, divider, icon_label, label, tool_button

log = logging.getLogger(__name__)

AUTOSAVE_INTERVAL_MS = 30_000


def _panel(title: str, *extra: QWidget) -> tuple[QWidget, QVBoxLayout]:
    panel = QWidget()
    panel.setObjectName("Panel")
    panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    lay = QVBoxLayout(panel)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    head = QHBoxLayout()
    head.setContentsMargins(SPACE.lg, SPACE.md, SPACE.md, SPACE.sm)
    head.setSpacing(SPACE.sm)
    head.addWidget(label(title, "brand"))
    head.addStretch(1)
    for w in extra:
        head.addWidget(w)
    lay.addLayout(head)
    return panel, lay


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or AppSettings.load(settings_file())
        self.show_model = Show()
        self.project_path: str | None = None
        self.dirty = False
        self._session_key = uuid.uuid4().hex
        self._autosave = AutosaveStore(autosave_dir())
        self._projection: ProjectionWindow | None = None
        self._probe_errors: dict[str, str] = {}

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1080, 680)
        self.resize(1440, 880)
        self.setAcceptDrops(True)

        self.thumbs = ThumbnailService(self)
        self.thumbs.probed.connect(self._on_probed)
        self.analyzer = MediaAnalyzer(self)
        self.analyzer.analyzed.connect(self._on_analyzed)
        self.system = system_info.collect(self.settings.projection_screen, self.settings.audio_device_id)
        self._devices = QMediaDevices(self)
        self._devices.audioOutputsChanged.connect(self.refresh_system)
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _s: self.refresh_system())
        app.screenRemoved.connect(lambda _s: self.refresh_system())
        app.primaryScreenChanged.connect(lambda _s: self.refresh_system())

        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_top_bar())

        body = QWidget()
        bl = QHBoxLayout(body)
        bl.setContentsMargins(SPACE.md, SPACE.md, SPACE.md, SPACE.md)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_cue_panel())
        splitter.addWidget(self._build_side())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([860, 520])
        bl.addWidget(splitter)
        outer.addWidget(body, 1)
        outer.addWidget(self._build_status_bar())

        self.toast = Toast(root)
        self._install_shortcuts()

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._write_autosave)
        self._autosave_timer.start()

        self.preview.set_preview_volume(self.settings.preview_volume)
        self._set_show(Show(), None)
        QTimer.singleShot(0, self.cue_view.setFocus)

    # ================================================================ UI
    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setFixedHeight(60)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(SPACE.lg, 0, SPACE.lg, 0)
        lay.setSpacing(SPACE.sm)
        lay.addWidget(Logo(30))
        lay.addSpacing(SPACE.xs)
        lay.addWidget(label(APP_NAME, "brand"))
        lay.addSpacing(SPACE.md)
        lay.addWidget(divider(vertical=True))
        lay.addSpacing(SPACE.sm)

        self.name_edit = QLineEdit()
        self.name_edit.setProperty("role", "title-edit")
        self.name_edit.setPlaceholderText("Nom du spectacle")
        self.name_edit.setMaxLength(120)
        self.name_edit.setMinimumWidth(180)
        self.name_edit.setMaximumWidth(420)
        self.name_edit.setToolTip("Cliquez pour renommer le spectacle")
        self.name_edit.editingFinished.connect(self._rename_show)
        lay.addWidget(self.name_edit, 1)
        self.dirty_label = label("● Non enregistré", "dirty")
        self.dirty_label.setToolTip("Le spectacle contient des modifications non enregistrées (Ctrl+S)")
        lay.addWidget(self.dirty_label)
        lay.addStretch(1)

        self.new_btn = tool_button("file-plus", "Nouveau spectacle (Ctrl+N)", 18)
        self.new_btn.clicked.connect(self.new_show)
        self.open_btn = tool_button("folder-open", "Ouvrir un spectacle (Ctrl+O)", 18)
        self.open_btn.clicked.connect(lambda: self.open_show())
        self.recent_btn = tool_button("chevron-down", "Spectacles récents", 14)
        self.recent_menu = QMenu(self)
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        self.recent_btn.setMenu(self.recent_menu)
        self.recent_btn.setPopupMode(self.recent_btn.ToolButtonPopupMode.InstantPopup)
        self.save_btn = tool_button("save", "Enregistrer (Ctrl+S)", 18)
        self.save_btn.clicked.connect(self.save)
        self.more_btn = tool_button("chevron-down", "Plus d'actions", 14)
        more = QMenu(self)
        more.addAction(icons.icon("save", COLORS.text_2), "Enregistrer sous…", self.save_as, QKeySequence("Ctrl+Shift+S"))
        more.addAction(icons.icon("search", COLORS.text_2), "Rechercher les fichiers manquants…", self.relink_missing)
        self.more_btn.setMenu(more)
        self.more_btn.setPopupMode(self.more_btn.ToolButtonPopupMode.InstantPopup)
        settings_btn = tool_button("settings", "Paramètres (Ctrl+,)", 18)
        settings_btn.clicked.connect(self.open_settings)
        for w in (self.new_btn, self.open_btn, self.recent_btn, self.save_btn, self.more_btn):
            lay.addWidget(w)
        lay.addSpacing(SPACE.xs)
        lay.addWidget(settings_btn)
        lay.addSpacing(SPACE.md)
        lay.addWidget(divider(vertical=True))
        lay.addSpacing(SPACE.md)
        self.check_btn = button("Vérifier la diffusion", "shield", "", tooltip="Diagnostic avant spectacle : médias, écran, son")
        self.check_btn.clicked.connect(self.open_diagnostic)
        lay.addWidget(self.check_btn)
        lay.addSpacing(SPACE.xs)
        self.launch_btn = button("Lancer le spectacle", "play", "launch", tooltip="Entrer en mode spectacle (F5)")
        self.launch_btn.setIconSize(QSize(14, 14))
        self.launch_btn.clicked.connect(self.launch_show)
        lay.addWidget(self.launch_btn)
        return bar

    def _build_cue_panel(self) -> QWidget:
        self.add_btn = button("Ajouter des vidéos", "plus", "primary", tooltip="Ajouter des vidéos (Ctrl+I)")
        self.add_btn.clicked.connect(self.add_videos)
        self.count_pill = Pill("0", "neutral")
        panel, lay = _panel("Conduite", self.count_pill, self.add_btn)
        self.cue_model = CueListModel(self.show_model, self)
        self.cue_view = CueListView()
        self.cue_view.setModel(self.cue_model)
        self.cue_view.setItemDelegate(CueDelegate(self.cue_model, self.cue_view))
        self.cue_view.selectionModel().currentChanged.connect(lambda cur, _prev: self._on_selected(cur.row()))
        self.cue_view.moveRequested.connect(self._move_cue)
        self.cue_view.filesDropped.connect(lambda paths, row: self._add_paths(paths, row))
        self.cue_view.deleteRequested.connect(self.delete_selected)
        self.cue_view.duplicateRequested.connect(self.duplicate_selected)
        self.cue_view.renameRequested.connect(lambda: self.editor.focus_name())
        self.cue_view.previewRequested.connect(lambda: self.preview.restart())
        self.cue_view.contextMenuRequested.connect(self._cue_context_menu)
        self.cue_view.doubleClicked.connect(lambda _i: self.editor.focus_name())
        self.empty = EmptyState()
        self.empty.addRequested.connect(self.add_videos)
        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(self.empty)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(SPACE.sm, 0, SPACE.sm, SPACE.sm)
        hl.addWidget(self.cue_view)
        self.list_stack.addWidget(holder)
        lay.addWidget(self.list_stack, 1)
        return panel

    def _build_side(self) -> QWidget:
        side = QSplitter(Qt.Orientation.Vertical)
        side.setChildrenCollapsible(False)
        self.preview = PreviewPanel(renderer=self.settings.render_mode, fit=self.settings.fit)
        self.preview.durationDetected.connect(self._on_duration_detected)
        preview_panel, pl = _panel("Prévisualisation", Pill("Hors conduite", "neutral"))
        pl.addWidget(self.preview, 1)
        self.editor = CueEditor()
        self.editor.cueEdited.connect(self._on_cue_edited)
        self.editor.renamed.connect(self._on_cue_renamed)
        self.dup_btn = tool_button("copy", "Dupliquer (Ctrl+D)", 16)
        self.dup_btn.clicked.connect(self.duplicate_selected)
        self.del_btn = tool_button("trash", "Supprimer (Suppr)", 16)
        self.del_btn.clicked.connect(self.delete_selected)
        props, ppl = _panel("Propriétés", self.dup_btn, self.del_btn)
        ppl.addWidget(self.editor, 1)
        side.addWidget(preview_panel)
        side.addWidget(props)
        side.setSizes([400, 520])
        return side

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setFixedHeight(34)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(SPACE.lg, 0, SPACE.lg, 0)
        lay.setSpacing(SPACE.sm)
        lay.addWidget(icon_label("film", COLORS.text_3, 14))
        self.st_count = label("", "caption")
        lay.addWidget(self.st_count)
        lay.addSpacing(SPACE.md)
        lay.addWidget(icon_label("clock", COLORS.text_3, 14))
        self.st_duration = label("", "caption")
        lay.addWidget(self.st_duration)
        lay.addSpacing(SPACE.md)
        self.st_missing_icon = icon_label("check-circle", COLORS.success, 14)
        lay.addWidget(self.st_missing_icon)
        self.st_missing = label("", "caption")
        lay.addWidget(self.st_missing)
        lay.addStretch(1)
        self.st_output_icon = icon_label("monitor", COLORS.text_3, 14)
        lay.addWidget(self.st_output_icon)
        self.st_output = label("", "caption")
        lay.addWidget(self.st_output)
        lay.addSpacing(SPACE.md)
        self.st_state = label("", "caption")
        lay.addWidget(self.st_state)
        lay.addSpacing(SPACE.md)
        lay.addWidget(label(f"{APP_NAME} {__version__}", "caption"))
        return bar

    def _install_shortcuts(self) -> None:
        def add(seq: str, slot) -> None:
            act = QAction(self)
            act.setShortcut(QKeySequence(seq))
            act.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            act.triggered.connect(slot)
            self.addAction(act)

        add("Ctrl+N", self.new_show)
        add("Ctrl+O", lambda: self.open_show())
        add("Ctrl+S", self.save)
        add("Ctrl+Shift+S", self.save_as)
        add("Ctrl+I", self.add_videos)
        add("Ctrl+,", self.open_settings)
        add("F5", self.launch_show)

    # ============================================================ état projet
    def _set_show(self, show: Show, path: str | None, dirty: bool = False) -> None:
        self.preview.set_cue(None)
        self.show_model = show
        self.project_path = path
        self._probe_errors.clear()
        self.cue_model.set_show(show)
        self.name_edit.setText(show.name)
        self.name_edit.setCursorPosition(0)
        self._set_dirty(dirty)
        self.refresh_statuses()
        for cue in show.cues:
            self._request_probe(cue)
        if show.cues:
            self.cue_view.setCurrentIndex(self.cue_model.index(0))
        else:
            self._on_selected(-1)

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self.dirty_label.setVisible(dirty)
        name = self.show_model.name or "Spectacle sans nom"
        self.setWindowTitle(f"{name}{' •' if dirty else ''} — {APP_NAME}")
        self._update_status_bar()

    def mark_dirty(self) -> None:
        self._set_dirty(True)

    def refresh_statuses(self) -> None:
        for cue in self.show_model.cues:
            self.cue_model.set_status(cue.id, self._status_for(cue))
        self._update_status_bar()

    def _status_for(self, cue: Cue) -> CueStatus:
        vs = video_status(cue)
        if vs is FileStatus.EMPTY:
            return CueStatus("error", "Sans vidéo")
        if vs is FileStatus.MISSING:
            return CueStatus("error", "Vidéo manquante")
        if vs is not FileStatus.OK:
            return CueStatus("error", "Illisible")
        if cue.video_path in self._probe_errors:
            return CueStatus("error", "Illisible")
        if cue.end_behavior is EndBehavior.IMAGE and cue.image_path and image_status(cue.image_path) is not FileStatus.OK:
            return CueStatus("warning", "Image manquante")
        probe = self.thumbs.result_for(cue.video_path)
        info = self.media_info_for(cue)
        detail = ""
        if info and info.video and info.video.display_size:
            detail = "{} × {}".format(*info.video.display_size)
        if probe is None or (info is None and self.analyzer.available):
            return CueStatus("neutral", "Analyse…", detail)
        verdict = self.assess(cue).verdict
        return CueStatus(verdict.kind, verdict.short, detail)

    # ------------------------------------------------- analyse des médias
    def media_info_for(self, cue: Cue) -> MediaInfo | None:
        if not cue.video_path:
            return None
        info = self.analyzer.result_for(cue.video_path)
        if info is None and not self.analyzer.available:
            probe = self.thumbs.result_for(cue.video_path)
            if probe is not None and probe.qt_meta:
                info = media_info_from_qt(cue.video_path, probe.qt_meta)
        return info

    def assess(self, cue: Cue, playback=None) -> Assessment:
        probe = self.thumbs.result_for(cue.video_path) if cue.video_path else None
        decode_ok = None if probe is None else probe.ok
        out = self.system.audio_output
        display = self.system.projection
        return assess_media(
            self.media_info_for(cue), decode_ok, probe.error if probe else "",
            display.physical_size if display else None, display.refresh_hz if display else None,
            out.max_channels if out else None, out.sample_rate if out else None, playback,
            "cpu" if self.preview.surface.renderer_name.startswith("Compat") else "gpu",
        )

    def refresh_system(self) -> None:
        self.system = system_info.collect(self.settings.projection_screen, self.settings.audio_device_id)
        self.refresh_statuses()
        self._show_in_editor(self.selected_cue())

    def _on_analyzed(self, info: MediaInfo) -> None:
        for cue in self.show_model.cues:
            if cue.video_path == info.path:
                if info.duration_ms and not cue.duration_ms:
                    cue.duration_ms = info.duration_ms
                self.cue_model.set_status(cue.id, self._status_for(cue))
                if self.selected_cue() is cue:
                    self._show_in_editor(cue)
        self._update_status_bar()

    def _update_status_bar(self) -> None:
        show = self.show_model
        n = len(show.cues)
        self.count_pill.setText(str(n))
        self.st_count.setText(f"{n} séquence{'s' if n > 1 else ''}")
        total = show.total_duration_ms()
        approx = "≈ " if show.has_unknown_durations() else ""
        self.st_duration.setText(f"Durée totale {approx}{format_duration_long(total)}" if n else "Durée totale —")
        missing = missing_file_count(show)
        unreadable = sum(1 for c in show.cues if c.video_path in self._probe_errors)
        if missing or unreadable:
            parts = []
            if missing:
                parts.append(f"{missing} fichier{'s' if missing > 1 else ''} manquant{'s' if missing > 1 else ''}")
            if unreadable:
                parts.append(f"{unreadable} vidéo{'s' if unreadable > 1 else ''} illisible{'s' if unreadable > 1 else ''}")
            self.st_missing.setText(" · ".join(parts))
            self.st_missing_icon.setPixmap(icons.pixmap("alert", COLORS.error, 14))
        else:
            self.st_missing.setText("Tous les fichiers sont disponibles" if n else "Aucun média")
            self.st_missing_icon.setPixmap(icons.pixmap("check-circle", COLORS.success if n else COLORS.text_3, 14))
        if self.project_path:
            state = "Modifications non enregistrées" if self.dirty else f"Enregistré · {Path(self.project_path).name}"
        else:
            state = "Nouveau spectacle, non enregistré" if (self.dirty or n) else "Nouveau spectacle"
        self.st_state.setText(state)
        self.list_stack.setCurrentIndex(1 if n else 0)
        self.launch_btn.setEnabled(n > 0)
        self.check_btn.setEnabled(n > 0)
        d = self.system.projection
        out = self.system.audio_output
        text = f"Sortie {d.physical_size[0]} × {d.physical_size[1]}" if d else "Sortie non détectée"
        if d and d.refresh_hz:
            text += f" · {fr_number(d.refresh_hz)} Hz"
        if out is None or self.system.audio_selected_missing:
            text += " · ⚠ sortie audio absente" if out is None else " · ⚠ sortie audio choisie absente"
        self.st_output.setText(text)
        self.st_output.setToolTip((d.describe() if d else "") + (f"\nAudio : {out.description} ({out.describe()})" if out else "\nAucune sortie audio"))

    # ============================================================== séquences
    def selected_cue(self) -> Cue | None:
        return self.cue_model.cue_at(self.cue_view.currentIndex().row())

    def _select(self, cue_id: str) -> None:
        row = self.cue_model.row_of(cue_id)
        if row >= 0:
            idx = self.cue_model.index(row)
            self.cue_view.setCurrentIndex(idx)
            self.cue_view.scrollTo(idx)

    def _on_selected(self, row: int) -> None:
        cue = self.cue_model.cue_at(row)
        self._show_in_editor(cue)
        self.preview.set_cue(cue)
        self._update_preview_poster(cue)
        self.dup_btn.setEnabled(cue is not None)
        self.del_btn.setEnabled(cue is not None)

    def _update_preview_poster(self, cue: Cue | None) -> None:
        probe = self.thumbs.result_for(cue.video_path) if cue and cue.video_path else None
        self.preview.set_poster(probe.thumbnail if probe and probe.ok else None)

    def _show_in_editor(self, cue: Cue | None) -> None:
        image = read_image(cue.image_path, max_side=640) if cue and cue.image_path else None
        self.editor.set_cue(cue, image)
        if cue is not None and cue.video_path in self._probe_errors:
            self.editor.set_probe_error(self._probe_errors[cue.video_path])
        if cue is not None:
            info = self.media_info_for(cue)
            analyzing = video_status(cue) is FileStatus.OK and (
                self.thumbs.result_for(cue.video_path) is None
                or (info is None and self.analyzer.available))
            assessment = self.assess(cue) if video_status(cue) is FileStatus.OK else None
            self.editor.set_media(info, assessment, self.system.projection, self.settings.fit, analyzing)

    def add_videos(self) -> None:
        start = str(Path(self.show_model.cues[-1].video_path).parent) if self.show_model.cues else (
            str(Path(self.project_path).parent) if self.project_path else "")
        paths, _ = QFileDialog.getOpenFileNames(self, "Ajouter des vidéos", start, VIDEO_FILTER)
        if paths:
            current = self.cue_view.currentIndex().row()
            self._add_paths(paths, current + 1 if current >= 0 else None)

    def _add_paths(self, paths: list[str], row: int | None = None) -> None:
        projects = [p for p in paths if p.lower().endswith(PROJECT_EXTENSION)]
        if projects:
            self.open_show(projects[0])
            return
        created = self.cue_model.add_videos([str(Path(p)) for p in paths], row)
        ignored = len(paths) - len(created)
        if not created:
            self.toast.show_message("Aucun fichier vidéo reconnu", "warning")
            return
        for cue in created:
            self._request_probe(cue)
        self.refresh_statuses()
        self.mark_dirty()
        self._select(created[0].id)
        self.cue_view.setFocus()
        paired = sum(1 for c in created if c.image_path)
        msg = f"{len(created)} séquence{'s' if len(created) > 1 else ''} ajoutée{'s' if len(created) > 1 else ''}"
        if paired:
            msg += f" · {paired} image{'s' if paired > 1 else ''} finale{'s' if paired > 1 else ''} associée{'s' if paired > 1 else ''}"
        if ignored:
            msg += f" · {ignored} fichier{'s' if ignored > 1 else ''} ignoré{'s' if ignored > 1 else ''}"
        self.toast.show_message(msg)

    def delete_selected(self) -> None:
        cue = self.selected_cue()
        if cue is None:
            return
        row = self.cue_view.currentIndex().row()
        if not dialogs.confirm(
            self, "Supprimer la séquence ?",
            f"« {cue.name} » sera retirée de la conduite. Les fichiers vidéo et image ne sont pas supprimés du disque.",
            "Supprimer", danger=True, icon_name="trash",
        ):
            return
        self.cue_model.remove(cue.id)
        self.refresh_statuses()
        self.mark_dirty()
        if self.show_model.cues:
            self.cue_view.setCurrentIndex(self.cue_model.index(min(row, len(self.show_model.cues) - 1)))
        else:
            self._on_selected(-1)
        self.toast.show_message(f"« {cue.name} » supprimée")

    def duplicate_selected(self) -> None:
        cue = self.selected_cue()
        if cue is None:
            return
        copy = self.cue_model.duplicate(cue.id)
        if copy:
            self.mark_dirty()
            self._update_status_bar()
            self._select(copy.id)

    def _move_cue(self, source: int, destination: int) -> None:
        if self.cue_model.move(source, destination):
            self.mark_dirty()
            self.cue_view.setCurrentIndex(self.cue_model.index(destination))

    def _cue_context_menu(self, pos) -> None:
        cue = self.selected_cue()
        menu = QMenu(self)
        if cue is not None:
            menu.addAction(icons.icon("play", COLORS.text_2), "Prévisualiser", self.preview.restart)
            menu.addAction(icons.icon("edit", COLORS.text_2), "Renommer", self.editor.focus_name, QKeySequence("F2"))
            menu.addAction(icons.icon("copy", COLORS.text_2), "Dupliquer", self.duplicate_selected, QKeySequence("Ctrl+D"))
            menu.addSeparator()
            row = self.cue_view.currentIndex().row()
            up = menu.addAction("Monter", lambda: self._move_cue(row, row - 1), QKeySequence("Alt+Up"))
            up.setEnabled(row > 0)
            down = menu.addAction("Descendre", lambda: self._move_cue(row, row + 1), QKeySequence("Alt+Down"))
            down.setEnabled(row < len(self.show_model.cues) - 1)
            menu.addSeparator()
            menu.addAction(icons.icon("trash", COLORS.error), "Supprimer…", self.delete_selected, QKeySequence("Delete"))
        else:
            menu.addAction(icons.icon("plus", COLORS.text_2), "Ajouter des vidéos…", self.add_videos)
        menu.exec(pos)

    def _on_cue_edited(self, cue_id: str, fields: dict) -> None:
        cue = self.show_model.cue_by_id(cue_id)
        if cue is None:
            return
        for key, value in fields.items():
            setattr(cue, key, value)
        if "video_path" in fields:
            self._probe_errors.pop(cue.video_path, None)
            self._request_probe(cue)
        self.cue_model.cue_changed(cue_id)
        self.cue_model.set_status(cue.id, self._status_for(cue))
        self.mark_dirty()
        if self.selected_cue() is cue:
            self._show_in_editor(cue)
            self.preview.refresh_cue(cue)
            self._update_preview_poster(cue)

    def _on_cue_renamed(self, cue_id: str, name: str) -> None:
        if self.cue_model.rename(cue_id, name):
            self.mark_dirty()

    def _rename_show(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setText(self.show_model.name)
            return
        self.name_edit.setCursorPosition(0)
        if name != self.show_model.name:
            self.show_model.name = name
            self.mark_dirty()

    # ============================================================= analyse
    def _request_probe(self, cue: Cue) -> None:
        if video_status(cue) is FileStatus.OK:
            self.thumbs.request(cue.video_path)
            self.analyzer.request(cue.video_path)

    def _on_probed(self, result: ProbeResult) -> None:
        if result.ok:
            self._probe_errors.pop(result.path, None)
        else:
            self._probe_errors[result.path] = result.error
        for cue in self.show_model.cues:
            if cue.video_path != result.path:
                continue
            if result.duration_ms and cue.duration_ms != result.duration_ms:
                cue.duration_ms = result.duration_ms
            self.cue_model.set_thumbnail(cue.id, result.thumbnail)
            self.cue_model.set_status(cue.id, self._status_for(cue))
            if self.selected_cue() is cue:
                self._show_in_editor(cue)
                self._update_preview_poster(cue)
        self._update_status_bar()

    def _on_duration_detected(self, cue_id: str, ms: int) -> None:
        cue = self.show_model.cue_by_id(cue_id)
        if cue is not None and cue.duration_ms != ms:
            cue.duration_ms = ms
            self.cue_model.cue_changed(cue_id)
            self._update_status_bar()

    # ============================================================== fichiers
    def maybe_save(self) -> bool:
        """True si l'on peut abandonner le spectacle courant."""
        if not self.dirty:
            return True
        choice = dialogs.ask_unsaved_changes(self, self.show_model.name)
        if choice == "save":
            return self.save()
        return choice == "discard"

    def new_show(self) -> None:
        if not self.maybe_save():
            return
        self._autosave.discard(self._session_key)
        self._set_show(Show(), None)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def open_show(self, path: str | None = None) -> bool:
        if not self.maybe_save():
            return False
        if path is None:
            start = str(Path(self.settings.recent_projects[0]).parent) if self.settings.recent_projects else ""
            path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un spectacle", start, PROJECT_FILTER)
            if not path:
                return False
        try:
            show = load_show(path)
        except ProjectError as exc:
            dialogs.inform(self, "Impossible d'ouvrir le spectacle", str(exc))
            self.settings.forget_recent(path)
            return False
        self._autosave.discard(self._session_key)
        self._set_show(show, str(Path(path)))
        self.settings.push_recent(path)
        self.settings.save(settings_file())
        missing = missing_file_count(show)
        if missing:
            self._warn_missing(missing)
        else:
            self.toast.show_message(f"« {show.name} » ouvert · {len(show.cues)} séquence(s)")
        return True

    def _warn_missing(self, missing: int) -> None:
        dlg = dialogs.StyledDialog(
            self, "Fichiers manquants",
            f"{missing} fichier{'s' if missing > 1 else ''} de ce spectacle "
            f"{'sont introuvables' if missing > 1 else 'est introuvable'}. Ils ont peut-être été déplacés ou renommés.",
            "alert", COLORS.warning)
        dlg.add_button("later", "Plus tard")
        dlg.add_button("search", "Rechercher dans un dossier…", "primary", default=True, icon_name="search")
        if dlg.ask() == "search":
            self.relink_missing()

    def relink_missing(self) -> None:
        if not missing_file_count(self.show_model):
            self.toast.show_message("Aucun fichier manquant")
            return
        start = str(Path(self.project_path).parent) if self.project_path else ""
        folder = QFileDialog.getExistingDirectory(self, "Rechercher les fichiers manquants dans…", start)
        if not folder:
            return
        fixed = self.cue_model.relink_missing(folder)
        if fixed:
            for cue in self.show_model.cues:
                self._request_probe(cue)
            self.mark_dirty()
        self.refresh_statuses()
        self._on_selected(self.cue_view.currentIndex().row())
        remaining = missing_file_count(self.show_model)
        self.toast.show_message(
            f"{fixed} fichier(s) retrouvé(s)" + (f" · {remaining} toujours manquant(s)" if remaining else ""),
            "warning" if remaining else "success")

    def save(self) -> bool:
        if not self.project_path:
            return self.save_as()
        return self._save_to(self.project_path)

    def save_as(self) -> bool:
        base = re.sub(r"[^\w\- ]+", "", self.show_model.name).strip().replace(" ", "_") or "spectacle"
        start_dir = Path(self.project_path).parent if self.project_path else (
            Path(self.show_model.cues[0].video_path).parent if self.show_model.cues and self.show_model.cues[0].video_path
            else Path.home())
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le spectacle", str(start_dir / f"{base}{PROJECT_EXTENSION}"),
                                              PROJECT_FILTER)
        if not path:
            return False
        if not path.lower().endswith(PROJECT_EXTENSION):
            path += PROJECT_EXTENSION
        return self._save_to(path)

    def _save_to(self, path: str) -> bool:
        self._rename_show()
        try:
            save_show(self.show_model, path)
        except ProjectError as exc:
            dialogs.inform(self, "Enregistrement impossible", str(exc))
            return False
        self.project_path = str(Path(path))
        self._autosave.discard(self._session_key)
        self.settings.push_recent(self.project_path)
        self.settings.save(settings_file())
        self._set_dirty(False)
        self.toast.show_message(f"Spectacle enregistré · {Path(path).name}")
        return True

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        recents = [p for p in self.settings.recent_projects]
        if not recents:
            act = self.recent_menu.addAction("Aucun spectacle récent")
            act.setEnabled(False)
            return
        for p in recents:
            exists = Path(p).is_file()
            act = self.recent_menu.addAction(icons.icon("recent", COLORS.text_2), Path(p).stem)
            act.setToolTip(p)
            act.setEnabled(exists)
            act.triggered.connect(lambda _=False, path=p: self.open_show(path))

    def _write_autosave(self) -> None:
        if self.dirty and self._projection is None:
            try:
                self._autosave.write(self._session_key, self.show_model, self.project_path)
            except OSError:
                log.warning("Autosauvegarde impossible", exc_info=True)

    def check_recovery(self) -> bool:
        """Propose la récupération d'une autosauvegarde. True si un spectacle a été restauré."""
        entries = self._autosave.entries()
        if not entries:
            return False
        entry = entries[0]
        choice = dialogs.ask_recovery(self, entry)
        if choice == "restore":
            try:
                show = AutosaveStore.load(entry)
            except Exception:
                log.exception("Autosauvegarde illisible")
                dialogs.inform(self, "Récupération impossible", "La copie de secours est endommagée.")
                return False
            path = entry.project_path if entry.project_path and Path(entry.project_path).parent.is_dir() else None
            self._set_show(show, path, dirty=True)
            AutosaveStore.remove(entry)
            self.toast.show_message("Spectacle récupéré — pensez à l'enregistrer", "warning", 4000)
            return True
        if choice == "discard":
            for e in entries:
                AutosaveStore.remove(e)
        return False

    def reopen_last(self) -> None:
        if self.settings.reopen_last_project and self.settings.recent_projects:
            last = self.settings.recent_projects[0]
            if Path(last).is_file():
                self.open_show(last)

    # ============================================================ paramètres
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.show_model.settings, self)
        if dlg.exec():
            self.settings = dlg.settings
            self.settings.save(settings_file())
            if dlg.show_settings is not None and dlg.show_settings != self.show_model.settings:
                self.show_model.settings = dlg.show_settings
                self.mark_dirty()
            self.preview.set_fit_mode(self.settings.fit)
            self.refresh_system()
            self.toast.show_message("Paramètres enregistrés")

    def open_diagnostic(self) -> None:
        if not self.show_model.cues:
            return
        from .diagnostic_dialog import DiagnosticDialog

        self.preview.stop()
        dlg = DiagnosticDialog(self, self)
        dlg.exec()

    # ========================================================== mode spectacle
    def launch_show(self) -> None:
        if self._projection is not None:
            return
        self._rename_show()
        if not self.show_model.cues:
            dialogs.inform(self, "Conduite vide", "Ajoutez au moins une séquence avant de lancer le spectacle.", "warning")
            return
        self.refresh_statuses()
        issues = validate_show(self.show_model, self._probe_errors)
        if self.settings.warn_missing_media and issues:
            if not dialogs.launch_check(self, issues):
                return
        elif any(i.severity is Severity.ERROR for i in issues):
            log.warning("Lancement avec %d problème(s) non signalé(s) (avertissement désactivé)", len(issues))
        if self.dirty:
            self._autosave.write(self._session_key, self.show_model, self.project_path)
        self.preview.stop()
        self.settings.preview_volume = self.preview.volume.value()
        log.info("Lancement du spectacle « %s »", self.show_model.name)
        self._projection = ProjectionWindow(self.show_model, self.settings)
        self._projection.exited.connect(self._on_show_exited)
        self.hide()  # aucune interface de préparation derrière la projection
        self._projection.start()

    def _on_show_exited(self) -> None:
        projection, self._projection = self._projection, None
        if projection is not None:
            projection.deleteLater()
        self.showMaximized() if self.isMaximized() else self.show()
        self.raise_()
        self.activateWindow()
        self.toast.show_message("Mode spectacle terminé", "info")

    # =============================================================== fenêtre
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        images = [p for p in paths if Path(p).suffix.lower() in IMAGE_EXTENSIONS]
        cue = self.selected_cue()
        if images and len(paths) == 1 and cue is not None:
            self._on_cue_edited(cue.id, {"image_path": str(Path(images[0])), "end_behavior": EndBehavior.IMAGE})
            self.toast.show_message("Image finale associée")
        else:
            self._add_paths(paths)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast._reposition()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._projection is not None:
            event.ignore()
            return
        if not self.maybe_save():
            event.ignore()
            return
        self.preview.stop()
        self.settings.preview_volume = self.preview.volume.value()
        self.settings.save(settings_file())
        self._autosave.discard(self._session_key)
        log.info("Fermeture de %s", APP_NAME)
        event.accept()

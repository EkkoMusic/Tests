"""Fenêtre des paramètres. Chaque option affichée est réellement appliquée."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, __version__
from app.core.keyboard_controller import ShowAction, bindings_from_config, describe_key, keys_for
from app.media.formats import IMAGE_FILTER
from app.media.playback_engine import audio_device_id
from app.models import EndOfShowBehavior, ShowSettings
from app.persistence.app_settings import AppSettings, FitMode
from app.utils.paths import logs_dir

from .theme import icons
from .theme.tokens import COLORS, SPACE
from .widgets.common import Toggle, button, divider, label, section_label


def _row(title: str, help_text: str, control: QWidget) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, SPACE.sm, 0, SPACE.sm)
    lay.setSpacing(SPACE.lg)
    texts = QVBoxLayout()
    texts.setSpacing(2)
    texts.addWidget(label(title))
    if help_text:
        texts.addWidget(label(help_text, "caption", wrap=True))
    lay.addLayout(texts, 1)
    lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return w


def _toggle(checked: bool) -> Toggle:
    return Toggle(checked)


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, show_settings: ShowSettings | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Paramètres — {APP_NAME}")
        self.setMinimumSize(760, 540)
        self.settings = deepcopy(settings)
        self.show_settings = deepcopy(show_settings) if show_settings is not None else None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav_box = QWidget()
        nav_box.setObjectName("Panel")
        nav_box.setFixedWidth(210)
        nav_box.setStyleSheet(f"#Panel {{ border-radius: 0; background: {COLORS.surface}; }}")
        nl = QVBoxLayout(nav_box)
        nl.setContentsMargins(SPACE.md, SPACE.xl, SPACE.md, SPACE.lg)
        nl.addWidget(label("Paramètres", "title"))
        nl.addSpacing(SPACE.md)
        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        nl.addWidget(self.nav, 1)
        nl.addWidget(label(f"{APP_NAME} {__version__}", "caption"))
        root.addWidget(nav_box)

        right = QVBoxLayout()
        right.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.lg)
        self.pages = QStackedWidget()
        right.addWidget(self.pages, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = button("Annuler")
        cancel.clicked.connect(self.reject)
        ok = button("Enregistrer", None, "primary")
        ok.setDefault(True)
        ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        right.addLayout(buttons)
        root.addLayout(right, 1)

        self._add_page("Général", "settings", self._general_page())
        self._add_page("Projection", "monitor", self._projection_page())
        self._add_page("Audio", "volume", self._audio_page())
        self._add_page("Sécurité", "shield", self._security_page())
        self._add_page("Clavier", "keyboard", self._keyboard_page())
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

    def _add_page(self, title: str, icon_name: str, page: QWidget) -> None:
        self.nav.addItem(QListWidgetItem(icons.icon(icon_name, COLORS.text_2), title))
        self.pages.addWidget(page)

    @staticmethod
    def _page(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACE.xs)
        lay.addWidget(label(title, "display"))
        lay.addWidget(label(subtitle, "muted", wrap=True))
        lay.addSpacing(SPACE.lg)
        return page, lay

    # -------------------------------------------------------------- pages
    def _general_page(self) -> QWidget:
        page, lay = self._page("Général", "Comportement de l'application au démarrage.")
        self.reopen = _toggle(self.settings.reopen_last_project)
        lay.addWidget(_row("Rouvrir le dernier spectacle", "Au lancement, le dernier fichier ouvert est rechargé.", self.reopen))
        lay.addWidget(divider())
        lay.addWidget(_row("Thème", "Thème sombre, conçu pour la pénombre de la régie.", label("Sombre", "muted")))
        lay.addWidget(divider())
        lay.addWidget(_row("Langue", "Interface entièrement en français.", label("Français", "muted")))
        lay.addWidget(divider())
        open_logs = button("Ouvrir le dossier", "folder-open")
        open_logs.clicked.connect(lambda: _open_folder(logs_dir()))
        lay.addWidget(_row("Journaux techniques", "Fichiers locaux utiles en cas d'incident.", open_logs))
        lay.addStretch(1)
        return page

    def _projection_page(self) -> QWidget:
        page, lay = self._page("Projection", "Ce que voit le public pendant le spectacle.")
        self.screen_combo = QComboBox()
        self.screen_combo.addItem("Écran principal", "")
        for screen in QGuiApplication.screens():
            g = screen.geometry()
            self.screen_combo.addItem(f"{screen.name()} — {g.width()}×{g.height()}", screen.name())
        idx = self.screen_combo.findData(self.settings.projection_screen)
        self.screen_combo.setCurrentIndex(max(0, idx))
        self.screen_combo.setMinimumWidth(220)
        lay.addWidget(_row("Écran de projection", "En mode « Dupliquer », un seul écran est visible : laissez « Écran principal ».",
                           self.screen_combo))
        lay.addWidget(divider())
        self.fit_combo = QComboBox()
        for mode in FitMode:
            self.fit_combo.addItem(mode.label, mode.value)
        self.fit_combo.setCurrentIndex(max(0, self.fit_combo.findData(self.settings.fit_mode)))
        lay.addWidget(_row("Proportions", "Les images ne sont jamais étirées. Les espaces libres sont noirs.", self.fit_combo))

        if self.show_settings is not None:
            lay.addSpacing(SPACE.lg)
            lay.addWidget(section_label("Ce spectacle"))
            standby = QWidget()
            sl = QHBoxLayout(standby)
            sl.setContentsMargins(0, 0, 0, 0)
            self.standby_edit = QLineEdit(self.show_settings.standby_image_path)
            self.standby_edit.setReadOnly(True)
            self.standby_edit.setPlaceholderText("Écran noir")
            self.standby_edit.setMinimumWidth(200)
            choose = button("Choisir…", "image")
            choose.clicked.connect(self._choose_standby)
            clear = button("", "x", "ghost", tooltip="Utiliser un écran noir")
            clear.clicked.connect(lambda: self.standby_edit.setText(""))
            sl.addWidget(self.standby_edit, 1)
            sl.addWidget(choose)
            sl.addWidget(clear)
            lay.addWidget(_row("Image d'attente", "Affichée à l'entrée en mode spectacle, avant la première séquence.", standby))
            lay.addWidget(divider())
            self.end_combo = QComboBox()
            for b in EndOfShowBehavior:
                self.end_combo.addItem(b.label, b.value)
            self.end_combo.setCurrentIndex(max(0, self.end_combo.findData(self.show_settings.end_of_show.value)))
            lay.addWidget(_row("Fin du spectacle", "Après la dernière séquence, à la flèche droite suivante.", self.end_combo))
        lay.addStretch(1)
        return page

    def _audio_page(self) -> QWidget:
        page, lay = self._page("Audio", "Son des vidéos pendant le spectacle.")
        vol = QWidget()
        vl = QHBoxLayout(vol)
        vl.setContentsMargins(0, 0, 0, 0)
        self.master = QSlider(Qt.Orientation.Horizontal)
        self.master.setRange(0, 100)
        self.master.setValue(self.settings.master_volume)
        self.master.setFixedWidth(180)
        value = label(f"{self.settings.master_volume} %", "mono")
        value.setMinimumWidth(42)
        self.master.valueChanged.connect(lambda v: value.setText(f"{v} %"))
        vl.addWidget(self.master)
        vl.addWidget(value)
        lay.addWidget(_row("Volume général", "Multiplié par le volume propre à chaque séquence.", vol))
        lay.addWidget(divider())
        self.device_combo = QComboBox()
        self.device_combo.addItem("Sortie système par défaut", "")
        for device in QMediaDevices.audioOutputs():
            self.device_combo.addItem(device.description(), audio_device_id(device))
        self.device_combo.setCurrentIndex(max(0, self.device_combo.findData(self.settings.audio_device_id)))
        self.device_combo.setMinimumWidth(240)
        lay.addWidget(_row("Sortie audio", "Si la sortie choisie disparaît, le son bascule sur la sortie par défaut.",
                           self.device_combo))
        lay.addStretch(1)
        return page

    def _security_page(self) -> QWidget:
        page, lay = self._page("Sécurité", "Protections contre les erreurs de manipulation.")
        self.confirm_exit = _toggle(self.settings.confirm_exit)
        lay.addWidget(_row("Confirmer la sortie du mode spectacle",
                           "Il faut presser deux fois Ctrl + Maj + Q en moins de 3 secondes. Rien n'est affiché au public.",
                           self.confirm_exit))
        lay.addWidget(divider())
        prot = QWidget()
        pl = QHBoxLayout(prot)
        pl.setContentsMargins(0, 0, 0, 0)
        self.repeat = _toggle(self.settings.repeat_protection)
        self.repeat_ms = QSpinBox()
        self.repeat_ms.setRange(100, 3000)
        self.repeat_ms.setSingleStep(100)
        self.repeat_ms.setSuffix(" ms")
        self.repeat_ms.setValue(self.settings.repeat_interval_ms)
        self.repeat_ms.setEnabled(self.settings.repeat_protection)
        self.repeat.toggled.connect(self.repeat_ms.setEnabled)
        pl.addWidget(self.repeat_ms)
        pl.addWidget(self.repeat)
        lay.addWidget(_row("Protection contre les commandes répétées",
                           "Ignore un second appui sur la même touche dans ce délai. Les touches maintenues sont toujours ignorées.",
                           prot))
        lay.addWidget(divider())
        self.warn_missing = _toggle(self.settings.warn_missing_media)
        lay.addWidget(_row("Avertir en cas de média manquant",
                           "Vérifie la conduite avant d'entrer en projection et signale les fichiers absents.",
                           self.warn_missing))
        lay.addStretch(1)
        return page

    def _keyboard_page(self) -> QWidget:
        page, lay = self._page("Clavier", "Commandes du mode spectacle. La personnalisation sera proposée dans une prochaine version.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACE.xl)
        grid.setVerticalSpacing(SPACE.md)
        bindings = bindings_from_config(self.settings.key_bindings)
        for row, action in enumerate(ShowAction):
            keys = QHBoxLayout()
            keys.setSpacing(SPACE.xs)
            for key in keys_for(bindings, action):
                for i, part in enumerate(describe_key(key).split(" + ")):
                    if i:
                        keys.addWidget(label("+", "caption"))
                    keys.addWidget(label(part, "kbd"))
            keys.addStretch(1)
            holder = QWidget()
            holder.setLayout(keys)
            grid.addWidget(holder, row, 0)
            grid.addWidget(label(action.label), row, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        lay.addSpacing(SPACE.lg)
        lay.addWidget(label(
            "Pour quitter, pressez deux fois Ctrl + Maj + Q en moins de 3 secondes (une seule fois si la "
            "confirmation est désactivée dans « Sécurité »). "
            "Ctrl + Maj + Échap est réservé par Windows (Gestionnaire des tâches) et ne peut pas être utilisé. "
            "Flèche droite est ignorée pendant la lecture et la pause : elle ne lance la séquence suivante "
            "que lorsque l'image finale (ou le noir) est affichée.",
            "caption", wrap=True))
        lay.addStretch(1)
        return page

    # -------------------------------------------------------------- actions
    def _choose_standby(self) -> None:
        start = str(Path(self.standby_edit.text()).parent) if self.standby_edit.text() else ""
        path, _ = QFileDialog.getOpenFileName(self, "Choisir l'image d'attente", start, IMAGE_FILTER)
        if path:
            self.standby_edit.setText(str(Path(path)))

    def _accept(self) -> None:
        s = self.settings
        s.reopen_last_project = self.reopen.isChecked()
        s.projection_screen = self.screen_combo.currentData() or ""
        s.fit_mode = self.fit_combo.currentData()
        s.master_volume = self.master.value()
        s.audio_device_id = self.device_combo.currentData() or ""
        s.confirm_exit = self.confirm_exit.isChecked()
        s.repeat_protection = self.repeat.isChecked()
        s.repeat_interval_ms = self.repeat_ms.value()
        s.warn_missing_media = self.warn_missing.isChecked()
        if self.show_settings is not None:
            self.show_settings.standby_image_path = self.standby_edit.text()
            self.show_settings.end_of_show = EndOfShowBehavior(self.end_combo.currentData())
        self.accept()


def _open_folder(path: Path) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

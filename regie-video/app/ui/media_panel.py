"""Panneau « Informations média » de la séquence sélectionnée."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.media.compatibility import Assessment, Severity, Verdict
from app.media.media_info import (
    MediaInfo,
    codec_label,
    format_aspect,
    format_bitrate,
    format_channels,
    format_colors,
    format_fps,
    format_sample_rate,
    format_size,
    fr_number,
)
from app.media.system_info import DisplayInfo
from app.persistence.app_settings import FitMode
from app.utils.timefmt import format_clock

from .theme import icons
from .theme.tokens import COLORS, SPACE
from .widgets.common import Pill, label, section_label
from .widgets.video_surface import target_rect

UNAVAILABLE = "Non disponible"


class RatioPreview(QWidget):
    """Schéma : le média (bleu) placé dans l'écran de projection, selon le mode choisi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._media: tuple[int, int] | None = None
        self._screen: tuple[int, int] = (1920, 1080)
        self._fit = FitMode.FIT
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_geometry_data(self, media: tuple[int, int] | None, screen: tuple[int, int] | None, fit: FitMode) -> None:
        self._media = media
        if screen and screen[0] and screen[1]:
            self._screen = screen
        self._fit = fit
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(260, 110)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sw, sh = self._screen
        avail = self.rect().adjusted(2, 2, -2, -18)
        scale = min(avail.width() / sw, avail.height() / sh)
        screen_rect = QRectF(avail.x() + (avail.width() - sw * scale) / 2, avail.y(), sw * scale, sh * scale)
        p.fillRect(screen_rect, QColor(COLORS.black))
        if self._media:
            mw, mh = self._media
            from PySide6.QtCore import QRect, QSize as _S

            area = QRect(0, 0, round(screen_rect.width()), round(screen_rect.height()))
            # Taille native : 1 pixel média = 1 pixel écran, à l'échelle du schéma.
            content = _S(mw, mh) if self._fit is not FitMode.NATIVE else _S(round(mw * scale), round(mh * scale))
            r = target_rect(content, area, self._fit)
            r.translate(screen_rect.topLeft())
            p.save()
            p.setClipRect(screen_rect)
            p.fillRect(r, QColor(115, 140, 255, 90))
            p.setPen(QPen(QColor(COLORS.accent), 1.2))
            p.drawRect(r.adjusted(0.5, 0.5, -0.5, -0.5))
            p.restore()
        p.setPen(QPen(QColor(COLORS.border_strong), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(screen_rect.adjusted(0.5, 0.5, -0.5, -0.5))
        f = QFont()
        f.setPixelSize(11)
        p.setFont(f)
        p.setPen(QColor(COLORS.text_3))
        caption = f"Écran {sw} × {sh}"
        if self._media:
            caption = f"Média {format_aspect(*self._media)} dans l'écran {format_aspect(sw, sh)}"
        p.drawText(QRectF(0, self.height() - 16, self.width(), 16), Qt.AlignmentFlag.AlignCenter, caption)


class _InfoGrid(QWidget):
    def __init__(self, rows: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(SPACE.lg)
        grid.setVerticalSpacing(SPACE.xs + 2)
        self._values: dict[str, QLabel] = {}
        for i, name in enumerate(rows):
            grid.addWidget(label(name, "caption"), i, 0, Qt.AlignmentFlag.AlignTop)
            value = QLabel(UNAVAILABLE)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(value, i, 1)
            self._values[name] = value
        grid.setColumnStretch(1, 1)

    def set(self, name: str, text: str | None) -> None:
        lbl = self._values[name]
        lbl.setText(text or UNAVAILABLE)
        lbl.setStyleSheet("" if text else f"color: {COLORS.text_3};")


class MediaInfoPanel(QWidget):
    VIDEO_ROWS = ["Résolution", "Format", "Cadence", "Codec", "Débit", "Taille", "Durée", "Couleurs"]
    AUDIO_ROWS = ["Codec", "Canaux", "Fréquence", "Débit"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACE.sm)

        head = QHBoxLayout()
        head.addWidget(section_label("Informations média"))
        head.addStretch(1)
        self.verdict = Pill("Analyse…", "neutral")
        head.addWidget(self.verdict)
        lay.addLayout(head)
        self.source = label("", "caption", wrap=True)
        lay.addWidget(self.source)

        self.ratio = RatioPreview()
        lay.addWidget(self.ratio)

        lay.addWidget(label("Vidéo", "muted"))
        self.video = _InfoGrid(self.VIDEO_ROWS)
        lay.addWidget(self.video)
        lay.addSpacing(SPACE.xs)
        lay.addWidget(label("Audio", "muted"))
        self.audio = _InfoGrid(self.AUDIO_ROWS)
        lay.addWidget(self.audio)
        self.no_audio = label("Aucune piste audio.", "caption")
        lay.addWidget(self.no_audio)
        lay.addSpacing(SPACE.xs)
        self.findings_box = QVBoxLayout()
        self.findings_box.setSpacing(SPACE.xs)
        lay.addLayout(self.findings_box)

    def _clear_findings(self) -> None:
        while self.findings_box.count():
            item = self.findings_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_finding(self, severity: Severity, text: str) -> None:
        icon_name, color = {
            Severity.BLOCKING: ("x-circle", COLORS.error),
            Severity.PERF: ("alert", COLORS.warning),
            Severity.WARNING: ("alert", COLORS.warning),
        }.get(severity, ("info", COLORS.text_3))
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(SPACE.sm)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, color, 14))
        ic.setAlignment(Qt.AlignmentFlag.AlignTop)
        rl.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        rl.addWidget(label(text, "caption", wrap=True), 1)
        self.findings_box.addWidget(row)

    def set_data(self, info: MediaInfo | None, assessment: Assessment | None, display: DisplayInfo | None,
                 fit: FitMode, analyzing: bool = False) -> None:
        self._clear_findings()
        screen = display.physical_size if display else None
        if assessment is not None and not analyzing:
            self.verdict.set_kind(assessment.verdict.kind, assessment.verdict.label)
        else:
            self.verdict.set_kind("neutral", "Analyse en cours…" if analyzing else "Non analysé")
        if info is None:
            self.source.setText("Analyse en cours…" if analyzing else "Aucune information disponible.")
        elif info.source == "ffprobe":
            self.source.setText("Valeurs lues dans le fichier (FFprobe).")
        elif info.source == "qt":
            self.source.setText("Analyse partielle (métadonnées du moteur de lecture) : FFprobe est indisponible.")
        else:
            self.source.setText(f"Analyse impossible : {info.error}" if info.error else "")

        v = info.video if info else None
        size = v.display_size if v else None
        self.ratio.set_geometry_data(size, screen, fit)
        if v and v.coded_width and v.coded_height:
            res = f"{v.coded_width} × {v.coded_height}"
            if size and size != (v.coded_width, v.coded_height):
                res += f"  →  affichée {size[0]} × {size[1]}"
            self.video.set("Résolution", res)
        else:
            self.video.set("Résolution", None)
        self.video.set("Format", format_aspect(*size) if size else None)
        cadence = format_fps(v.fps) if v else None
        if cadence and v and v.variable_frame_rate:
            cadence += " (variable)"
        if cadence and v and v.is_interlaced:
            cadence += " · entrelacée"
        self.video.set("Cadence", cadence)
        codec = codec_label(v.codec, v.profile) if v else None
        self.video.set("Codec", codec)
        rate = format_bitrate(v.bit_rate) if v else None
        if rate and info and info.video_bit_rate_estimated:
            rate = f"≈ {rate} (estimé)"
        self.video.set("Débit", rate)
        self.video.set("Taille", format_size(info.size_bytes) if info else None)
        self.video.set("Durée", format_clock(info.duration_ms) if info and info.duration_ms else None)
        self.video.set("Couleurs", format_colors(v) if v and info and info.source == "ffprobe" else None)

        a = info.primary_audio if info else None
        has_audio = a is not None
        self.audio.setVisible(has_audio or info is None)
        self.no_audio.setVisible(info is not None and not has_audio and info.ok)
        self.audio.set("Codec", codec_label(a.codec, a.profile) if a else None)
        self.audio.set("Canaux", format_channels(a) if a else None)
        freq = format_sample_rate(a.sample_rate) if a else None
        if freq and a and a.bit_depth:
            freq += f" · {a.bit_depth} bits"
        self.audio.set("Fréquence", freq)
        self.audio.set("Débit", format_bitrate(a.bit_rate) if a else None)

        if assessment is not None and not analyzing:
            order = {Severity.BLOCKING: 0, Severity.PERF: 1, Severity.WARNING: 2, Severity.INFO: 3}
            for f in sorted(assessment.findings, key=lambda f: order[f.severity]):
                self._add_finding(f.severity, f.message)
            if assessment.verdict is Verdict.VERIFIED:
                self._add_finding(Severity.INFO, "Décodage vérifié par le moteur de lecture. La fluidité se confirme "
                                                 "avec « Vérifier la diffusion » sur le PC du spectacle.")
            elif assessment.verdict is Verdict.PRESUMED:
                self._add_finding(Severity.INFO, "À confirmer par un test de lecture (« Vérifier la diffusion »).")


def display_summary(display: DisplayInfo | None) -> str:
    if display is None:
        return "Sortie non détectée"
    return f"Sortie {display.describe()}"


__all__ = ["MediaInfoPanel", "RatioPreview", "display_summary", "fr_number"]

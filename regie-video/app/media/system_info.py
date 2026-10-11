"""Capacités du système : écrans de projection, sorties audio, outils.

La résolution du média et celle de la projection sont deux informations
distinctes : ce module ne décrit que la sortie (ce que Windows annonce).
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import qVersion
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtMultimedia import QAudioDevice, QAudioFormat, QMediaDevices

from .media_info import ffprobe_version, find_ffprobe, fr_number


@dataclass
class DisplayInfo:
    name: str
    logical_width: int
    logical_height: int
    scale: float
    refresh_hz: float | None
    primary: bool = False

    @property
    def physical_size(self) -> tuple[int, int]:
        """Pixels réels envoyés à l'écran (mise à l'échelle Windows prise en compte)."""
        return round(self.logical_width * self.scale), round(self.logical_height * self.scale)

    def describe(self) -> str:
        w, h = self.physical_size
        parts = [f"{w} × {h}"]
        if self.refresh_hz:
            parts.append(f"{fr_number(self.refresh_hz)} Hz")
        parts.append(f"mise à l'échelle {fr_number(self.scale * 100, 0)} %")
        return " · ".join(parts)


@dataclass
class AudioOutputInfo:
    id: str
    description: str
    is_default: bool
    sample_rate: int | None
    channels: int | None
    max_channels: int | None
    sample_format: str | None

    def describe(self) -> str:
        parts = []
        if self.sample_rate:
            parts.append(f"{fr_number(self.sample_rate / 1000, 1)} kHz")
        if self.channels:
            parts.append({1: "mono", 2: "stéréo"}.get(self.channels, f"{self.channels} canaux"))
        if self.max_channels and self.max_channels != self.channels:
            parts.append(f"jusqu'à {self.max_channels} canaux")
        if self.sample_format:
            parts.append(self.sample_format)
        return " · ".join(parts) or "format non communiqué"


@dataclass
class SystemInfo:
    displays: list[DisplayInfo] = field(default_factory=list)
    projection: DisplayInfo | None = None
    audio_outputs: list[AudioOutputInfo] = field(default_factory=list)
    audio_output: AudioOutputInfo | None = None   # sortie réellement utilisée
    audio_selected_missing: bool = False           # la sortie choisie a disparu
    ffprobe_path: str | None = None
    ffprobe_version: str | None = None
    cpu_count: int = 0
    os_name: str = ""
    qt_version: str = ""


_SAMPLE_FORMATS = {
    QAudioFormat.SampleFormat.UInt8: "8 bits",
    QAudioFormat.SampleFormat.Int16: "16 bits",
    QAudioFormat.SampleFormat.Int32: "32 bits",
    QAudioFormat.SampleFormat.Float: "32 bits flottant",
}


def display_from_screen(screen: QScreen, primary: QScreen | None) -> DisplayInfo:
    g = screen.geometry()
    rate = screen.refreshRate()
    return DisplayInfo(screen.name(), g.width(), g.height(), screen.devicePixelRatio(),
                       round(rate, 3) if rate and rate > 1 else None, screen is primary)


def audio_device_id(device: QAudioDevice) -> str:
    return bytes(device.id().data()).decode(errors="replace")


def audio_from_device(device: QAudioDevice, default_id: str) -> AudioOutputInfo:
    fmt = device.preferredFormat()
    return AudioOutputInfo(
        id=audio_device_id(device),
        description=device.description(),
        is_default=audio_device_id(device) == default_id,
        sample_rate=fmt.sampleRate() or None,
        channels=fmt.channelCount() or None,
        max_channels=device.maximumChannelCount() or None,
        sample_format=_SAMPLE_FORMATS.get(fmt.sampleFormat()),
    )


def collect(projection_screen: str = "", audio_device: str = "", with_ffprobe: bool = True) -> SystemInfo:
    info = SystemInfo(cpu_count=os.cpu_count() or 0, os_name=f"{platform.system()} {platform.release()}",
                      qt_version=f"Qt {qVersion()} · PySide6 {PYSIDE_VERSION}")
    primary = QGuiApplication.primaryScreen()
    for screen in QGuiApplication.screens():
        d = display_from_screen(screen, primary)
        info.displays.append(d)
        if projection_screen and screen.name() == projection_screen:
            info.projection = d
    if info.projection is None:
        info.projection = next((d for d in info.displays if d.primary), info.displays[0] if info.displays else None)
    default = QMediaDevices.defaultAudioOutput()
    default_id = audio_device_id(default) if not default.isNull() else ""
    for device in QMediaDevices.audioOutputs():
        info.audio_outputs.append(audio_from_device(device, default_id))
    chosen = next((a for a in info.audio_outputs if audio_device and a.id == audio_device), None)
    info.audio_selected_missing = bool(audio_device) and chosen is None
    info.audio_output = chosen or next((a for a in info.audio_outputs if a.is_default), None) or (
        info.audio_outputs[0] if info.audio_outputs else None)
    if with_ffprobe:
        info.ffprobe_path = find_ffprobe()
        info.ffprobe_version = ffprobe_version(info.ffprobe_path) if info.ffprobe_path else None
    return info

"""Caractéristiques techniques des médias (vidéo et audio).

Source principale : **FFprobe**, exécuté dans un processus séparé (un fichier
corrompu ne peut pas faire planter l'application, et un délai maximal
s'applique). FFprobe ne sert qu'au diagnostic : la lecture reste assurée par
le moteur Qt Multimedia.

Source de repli : les métadonnées exposées par Qt Multimedia, moins
complètes (pas de profil, de profondeur de couleur ni de nombre de canaux).
Toute valeur inconnue reste ``None`` : rien n'est jamais inventé.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PROBE_TIMEOUT_S = 20


# ======================================================================= modèle
@dataclass
class VideoStreamInfo:
    codec: str | None = None              # nom court FFmpeg : h264, hevc, prores…
    codec_long: str | None = None
    profile: str | None = None
    level: int | None = None
    coded_width: int | None = None        # pixels stockés
    coded_height: int | None = None
    sar: Fraction | None = None           # rapport d'aspect des pixels
    rotation: int = 0                     # degrés (sens horaire), 0/90/180/270
    fps: Fraction | None = None           # cadence moyenne
    r_fps: Fraction | None = None         # cadence nominale (r_frame_rate)
    bit_rate: int | None = None
    bit_depth: int | None = None
    pix_fmt: str | None = None
    chroma: str | None = None             # 4:2:0, 4:2:2, 4:4:4
    color_space: str | None = None        # bt709, bt2020nc…
    color_primaries: str | None = None
    color_transfer: str | None = None     # bt709, smpte2084 (PQ), arib-std-b67 (HLG)
    color_range: str | None = None        # tv (limitée) / pc (complète)
    field_order: str | None = None        # progressive, tt, bb…
    frame_count: int | None = None

    @property
    def display_size(self) -> tuple[int, int] | None:
        """Taille affichée : pixels non carrés corrigés, rotation appliquée."""
        if not self.coded_width or not self.coded_height:
            return None
        w, h = self.coded_width, self.coded_height
        if self.sar and self.sar > 0 and self.sar != 1:
            w = round(w * self.sar)
        if self.rotation % 180 == 90:
            w, h = h, w
        return w, h

    @property
    def display_aspect(self) -> float | None:
        size = self.display_size
        return size[0] / size[1] if size else None

    @property
    def hdr(self) -> str | None:
        if self.color_transfer == "smpte2084":
            return "HDR10 (PQ)"
        if self.color_transfer == "arib-std-b67":
            return "HLG"
        if self.color_transfer:
            return None
        return None

    @property
    def is_interlaced(self) -> bool:
        return bool(self.field_order) and self.field_order not in ("progressive", "unknown")

    @property
    def variable_frame_rate(self) -> bool:
        if not self.fps or not self.r_fps:
            return False
        return abs(float(self.fps) - float(self.r_fps)) / float(self.r_fps) > 0.01

    @property
    def pixel_rate(self) -> float | None:
        """Pixels à décoder par seconde (indicateur de charge)."""
        if not self.coded_width or not self.coded_height or not self.fps:
            return None
        return self.coded_width * self.coded_height * float(self.fps)


@dataclass
class AudioStreamInfo:
    codec: str | None = None
    codec_long: str | None = None
    profile: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None
    bit_rate: int | None = None
    sample_fmt: str | None = None
    bit_depth: int | None = None


@dataclass
class MediaInfo:
    path: str
    source: str = "none"                  # ffprobe | qt | none
    ok: bool = False
    error: str = ""
    container: str | None = None
    size_bytes: int | None = None
    duration_ms: int | None = None
    overall_bit_rate: int | None = None
    video: VideoStreamInfo | None = None
    audio: list[AudioStreamInfo] = field(default_factory=list)
    video_stream_count: int = 0
    video_bit_rate_estimated: bool = False

    @property
    def partial(self) -> bool:
        return self.source == "qt"

    @property
    def primary_audio(self) -> AudioStreamInfo | None:
        return self.audio[0] if self.audio else None


# ===================================================================== FFprobe
def find_ffprobe() -> str | None:
    """FFprobe livré avec l'application, sinon celui du système."""
    exe = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    override = os.environ.get("REGIE_VIDEO_FFPROBE")
    if override:
        return override if Path(override).is_file() else None
    from app.utils.paths import app_root

    root = app_root()
    for candidate in (root / "ffmpeg" / exe, root / "vendor" / "ffmpeg" / exe, Path(sys.executable).parent / "ffmpeg" / exe):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ffprobe")


def ffprobe_version(ffprobe: str | None = None) -> str | None:
    ffprobe = ffprobe or find_ffprobe()
    if not ffprobe:
        return None
    try:
        out = subprocess.run([ffprobe, "-version"], capture_output=True, text=True, timeout=5,
                             **_no_window()).stdout
        return out.splitlines()[0].replace("ffprobe version ", "").split(" Copyright")[0] if out else None
    except Exception:
        return None


def _no_window() -> dict:
    # Sous Windows, aucune fenêtre de console ne doit apparaître (projection !).
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


def run_ffprobe(path: str, ffprobe: str | None = None, timeout: float = PROBE_TIMEOUT_S) -> dict[str, Any]:
    ffprobe = ffprobe or find_ffprobe()
    if not ffprobe:
        raise FileNotFoundError("FFprobe introuvable")
    cmd = [ffprobe, "-v", "error", "-hide_banner", "-print_format", "json",
           "-show_format", "-show_streams", "-show_error", path]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, **_no_window())
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace") or "{}")
    except json.JSONDecodeError:
        data = {}
    if proc.returncode != 0 and not data.get("streams"):
        message = (data.get("error") or {}).get("string") or proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"FFprobe a échoué (code {proc.returncode})")
    return data


def _int(value: Any) -> int | None:
    try:
        v = int(str(value).strip())
        return v if v >= 0 else None
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fraction(value: Any) -> Fraction | None:
    """« 24000/1001 » → Fraction ; « 0/0 » ou valeur absente → None."""
    if not value or not isinstance(value, str):
        return None
    try:
        if ":" in value:
            num, den = value.split(":")
        elif "/" in value:
            num, den = value.split("/")
        else:
            num, den = value, "1"
        num, den = int(num), int(den)
        if num <= 0 or den <= 0:
            return None
        return Fraction(num, den)
    except (ValueError, ZeroDivisionError):
        return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in ("", "unknown", "n/a", "none", "und", "reserved", "unspecified") else text


_CHROMA = {"420": "4:2:0", "422": "4:2:2", "444": "4:4:4", "411": "4:1:1", "440": "4:4:0"}


def _pix_fmt_details(pix_fmt: str | None) -> tuple[int | None, str | None]:
    """« yuv420p10le » → (10, « 4:2:0 ») ; « yuv444p » → (8, « 4:4:4 »)."""
    if not pix_fmt:
        return None, None
    import re

    chroma = None
    m = re.search(r"yuv[aj]?(4\d\d)", pix_fmt)
    if m:
        chroma = _CHROMA.get(m.group(1))
    elif pix_fmt.startswith(("nv12", "nv21")):
        chroma = "4:2:0"
    elif pix_fmt.startswith(("p010", "p016")):
        chroma = "4:2:0"
    elif pix_fmt.startswith(("rgb", "bgr", "gbr", "argb", "abgr", "rgba", "bgra")):
        chroma = "RVB"
    depth = None
    m = re.search(r"p(\d{1,2})(le|be)?$", pix_fmt)
    if m and m.group(1) not in ("4",):
        depth = int(m.group(1))
    elif pix_fmt.startswith(("p010",)):
        depth = 10
    elif pix_fmt.startswith(("p016",)):
        depth = 16
    elif pix_fmt.startswith(("yuv", "yuvj", "nv12", "nv21", "gbrp")) or pix_fmt in ("rgb24", "bgr24", "rgba", "bgra", "argb", "abgr"):
        depth = 8
    return depth, chroma


def _rotation(stream: dict[str, Any]) -> int:
    rot = None
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            rot = _float(side.get("rotation"))
    if rot is None:
        rot = _float((stream.get("tags") or {}).get("rotate"))
    if rot is None:
        return 0
    # FFprobe exprime la rotation de la matrice d'affichage (sens trigonométrique).
    return int(round(-rot)) % 360


def _stream_bit_rate(stream: dict[str, Any]) -> int | None:
    rate = _int(stream.get("bit_rate"))
    if rate:
        return rate
    tags = stream.get("tags") or {}
    for key in ("BPS", "BPS-eng", "bit_rate"):
        rate = _int(tags.get(key))
        if rate:
            return rate
    return None


def parse_ffprobe(data: dict[str, Any], path: str) -> MediaInfo:
    info = MediaInfo(path=path, source="ffprobe", ok=True)
    fmt = data.get("format") or {}
    info.container = _clean(fmt.get("format_long_name")) or _clean(fmt.get("format_name"))
    info.size_bytes = _int(fmt.get("size"))
    duration = _float(fmt.get("duration"))
    info.overall_bit_rate = _int(fmt.get("bit_rate"))
    streams = data.get("streams") or []
    videos = [s for s in streams if s.get("codec_type") == "video"
              and not (s.get("disposition") or {}).get("attached_pic")]
    info.video_stream_count = len(videos)
    if videos:
        s = videos[0]
        v = VideoStreamInfo(
            codec=_clean(s.get("codec_name")),
            codec_long=_clean(s.get("codec_long_name")),
            profile=_clean(s.get("profile")),
            level=_int(s.get("level")) if _int(s.get("level")) not in (None, 0) else None,
            coded_width=_int(s.get("width")) or None,
            coded_height=_int(s.get("height")) or None,
            sar=_fraction(s.get("sample_aspect_ratio")),
            rotation=_rotation(s),
            fps=_fraction(s.get("avg_frame_rate")) or _fraction(s.get("r_frame_rate")),
            r_fps=_fraction(s.get("r_frame_rate")),
            bit_rate=_stream_bit_rate(s),
            pix_fmt=_clean(s.get("pix_fmt")),
            color_space=_clean(s.get("color_space")),
            color_primaries=_clean(s.get("color_primaries")),
            color_transfer=_clean(s.get("color_transfer")),
            color_range=_clean(s.get("color_range")),
            field_order=_clean(s.get("field_order")),
            frame_count=_int(s.get("nb_frames")),
        )
        depth, chroma = _pix_fmt_details(v.pix_fmt)
        v.bit_depth = _int(s.get("bits_per_raw_sample")) or depth
        v.chroma = chroma
        info.video = v
        if duration is None:
            duration = _float(s.get("duration"))
    for s in streams:
        if s.get("codec_type") != "audio":
            continue
        sample_fmt = _clean(s.get("sample_fmt"))
        info.audio.append(AudioStreamInfo(
            codec=_clean(s.get("codec_name")),
            codec_long=_clean(s.get("codec_long_name")),
            profile=_clean(s.get("profile")),
            sample_rate=_int(s.get("sample_rate")) or None,
            channels=_int(s.get("channels")) or None,
            channel_layout=_clean(s.get("channel_layout")),
            bit_rate=_stream_bit_rate(s),
            sample_fmt=sample_fmt,
            bit_depth=_int(s.get("bits_per_raw_sample")) or _int(s.get("bits_per_sample")) or None,
        ))
    if duration is not None and duration > 0:
        info.duration_ms = int(round(duration * 1000))
    if info.video and info.video.bit_rate is None and info.overall_bit_rate:
        # Débit global moins l'audio : estimation signalée comme telle à l'affichage.
        audio = sum(a.bit_rate or 0 for a in info.audio)
        info.video_bit_rate_estimated = True
        info.video.bit_rate = max(0, info.overall_bit_rate - audio) or None
    return info


def probe_file(path: str, ffprobe: str | None = None) -> MediaInfo:
    """Analyse un fichier. Ne lève jamais d'exception : voir ``ok`` et ``error``."""
    info = MediaInfo(path=path)
    try:
        info.size_bytes = os.path.getsize(path)
    except OSError as exc:
        info.error = f"fichier inaccessible ({exc.strerror or exc})"
        return info
    tool = ffprobe or find_ffprobe()
    if not tool:
        info.error = "FFprobe indisponible"
        return info
    try:
        result = parse_ffprobe(run_ffprobe(path, tool), path)
    except subprocess.TimeoutExpired:
        info.error = "analyse trop longue (délai dépassé)"
        return info
    except Exception as exc:
        detail = str(exc).strip()
        info.error = f"fichier illisible ou endommagé ({detail})" if detail else "analyse impossible"
        return info
    if result.size_bytes is None:
        result.size_bytes = info.size_bytes
    if result.video is None:
        result.error = "aucune piste vidéo"
    return result


# ============================================================ formatage (FR)
def fr_number(value: float, decimals: int = 2) -> str:
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".") if decimals else f"{value:.0f}"
    return text.replace(".", ",")


def format_fps(fps: Fraction | None) -> str | None:
    if not fps:
        return None
    if fps.denominator == 1:
        return f"{fps.numerator} i/s"
    if fps.denominator == 1001:
        return f"{fr_number(float(fps), 3)} i/s ({fps.numerator}/1001)"
    return f"{fr_number(float(fps), 3)} i/s"


def format_aspect(width: int, height: int) -> str:
    """3289 × 1480 → « 2,22:1 » ; 1920 × 1080 → « 16:9 (1,78:1) » ; 1080 × 1920 → « 9:16 (vertical) »."""
    if not width or not height:
        return "—"
    ratio = width / height
    for value, name in ((16 / 9, "16:9"), (4 / 3, "4:3"), (3 / 2, "3:2"), (1.0, "1:1"),
                        (9 / 16, "9:16"), (3 / 4, "3:4")):
        if abs(ratio - value) < 0.006:
            if ratio < 1:
                return f"{name} (vertical)"
            return name if value == 1.0 else f"{name} ({fr_number(ratio)}:1)"
    if ratio < 1:
        return f"1:{fr_number(1 / ratio)} (vertical)"
    return f"{fr_number(ratio)}:1"


def format_bitrate(bps: int | None) -> str | None:
    if not bps:
        return None
    if bps >= 1_000_000:
        return f"{fr_number(bps / 1_000_000, 1)} Mbit/s"
    return f"{fr_number(bps / 1000, 0)} kbit/s"


def format_size(n: int | None) -> str | None:
    if n is None:
        return None
    for unit, factor in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("ko", 1024)):
        if n >= factor:
            return f"{fr_number(n / factor, 2 if unit == 'Go' else 1)} {unit}"
    return f"{n} octets"


_CODEC_NAMES = {
    "h264": "H.264 / AVC", "hevc": "H.265 / HEVC", "av1": "AV1", "vp9": "VP9", "vp8": "VP8",
    "prores": "Apple ProRes", "dnxhd": "Avid DNxHD/HR", "mpeg2video": "MPEG-2", "mpeg4": "MPEG-4 Part 2",
    "mjpeg": "Motion JPEG", "ffv1": "FFV1", "cfhd": "GoPro CineForm", "hap": "HAP", "qtrle": "QuickTime Animation",
    "aac": "AAC", "mp3": "MP3", "ac3": "Dolby Digital (AC-3)", "eac3": "Dolby Digital Plus (E-AC-3)",
    "opus": "Opus", "vorbis": "Vorbis", "flac": "FLAC", "alac": "Apple Lossless", "dts": "DTS", "truehd": "Dolby TrueHD",
}


def codec_label(codec: str | None, profile: str | None = None) -> str | None:
    if not codec:
        return None
    if codec.startswith("pcm_"):
        name = f"PCM non compressé ({codec[4:]})"
    else:
        name = _CODEC_NAMES.get(codec, codec.upper())
    return f"{name} · {profile}" if profile else name


_SPACES = {"bt709": "BT.709", "bt470bg": "BT.601", "smpte170m": "BT.601", "bt2020nc": "BT.2020", "bt2020c": "BT.2020",
           "bt2020": "BT.2020", "smpte240m": "SMPTE 240M", "gbr": "RVB", "rgb": "RVB", "fcc": "FCC", "ycgco": "YCgCo"}


def format_colors(v: VideoStreamInfo) -> str | None:
    parts = []
    space = _SPACES.get(v.color_space or v.color_primaries or "", v.color_space)
    if space:
        parts.append(space)
    parts.append(v.hdr or ("SDR" if v.color_transfer else "SDR (non signalé)"))
    if v.color_range == "tv":
        parts.append("plage limitée")
    elif v.color_range == "pc":
        parts.append("plage complète")
    if v.bit_depth:
        parts.append(f"{v.bit_depth} bits")
    if v.chroma:
        parts.append(v.chroma)
    return " · ".join(parts) if parts else None


_LAYOUTS = {"mono": "Mono", "stereo": "Stéréo", "2.1": "2.1", "quad": "Quadriphonie", "5.0": "5.0", "5.1": "5.1",
            "5.1(side)": "5.1", "6.1": "6.1", "7.1": "7.1", "7.1(wide)": "7.1"}


def format_channels(a: AudioStreamInfo) -> str | None:
    if not a.channels:
        return None
    if a.channel_layout and a.channel_layout in _LAYOUTS:
        return f"{_LAYOUTS[a.channel_layout]} ({a.channels} canaux)" if a.channels > 2 else _LAYOUTS[a.channel_layout]
    return {1: "Mono", 2: "Stéréo"}.get(a.channels, f"{a.channels} canaux")


def format_sample_rate(rate: int | None) -> str | None:
    return f"{fr_number(rate / 1000, 1)} kHz" if rate else None


def media_info_from_qt(path: str, meta: dict[str, Any]) -> MediaInfo:
    """Repli quand FFprobe est absent : métadonnées fournies par Qt Multimedia.

    ``meta`` : resolution (w, h), fps (float), video_codec, audio_codec (str),
    video_bit_rate, audio_bit_rate (int), duration_ms (int), has_audio (bool).
    """
    info = MediaInfo(path=path, source="qt", ok=True)
    try:
        info.size_bytes = os.path.getsize(path)
    except OSError:
        pass
    info.duration_ms = _int(meta.get("duration_ms")) or None
    res = meta.get("resolution")
    if res and res[0] and res[1]:
        fps = meta.get("fps")
        info.video = VideoStreamInfo(
            codec=_clean(meta.get("video_codec")),
            coded_width=int(res[0]),
            coded_height=int(res[1]),
            fps=Fraction(fps).limit_denominator(1001) if fps else None,
            bit_rate=_int(meta.get("video_bit_rate")) or None,
        )
        info.video_stream_count = 1
    if meta.get("has_audio"):
        info.audio.append(AudioStreamInfo(codec=_clean(meta.get("audio_codec")),
                                          bit_rate=_int(meta.get("audio_bit_rate")) or None))
    if info.video is None:
        info.ok = False
        info.error = "aucune piste vidéo détectée"
    return info

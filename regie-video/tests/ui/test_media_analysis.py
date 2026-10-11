"""Analyse réelle des médias de test : FFprobe, décodage Qt, gros fichiers, haut débit.

Les tests FFprobe sont ignorés si l'outil est absent (il est livré avec
l'exécutable Windows et installé par la CI).
"""

import os
import shutil
import subprocess
import time
from fractions import Fraction

import pytest

from app.media.compatibility import Verdict, assess_media
from app.media.media_info import find_ffprobe, probe_file
from app.media.playback_engine import QtPlaybackEngine
from app.media.thumbnail_service import ThumbnailService

pytestmark = pytest.mark.media
needs_ffprobe = pytest.mark.skipif(find_ffprobe() is None, reason="FFprobe indisponible")


@pytest.fixture
def media_dir(fixtures_dir):
    return fixtures_dir / "media"


@needs_ffprobe
@pytest.mark.parametrize("name, size, display", [
    ("res_1920x1080.mp4", (1920, 1080), (1920, 1080)),
    ("res_3840x2160.mp4", (3840, 2160), (3840, 2160)),
    ("res_3289x1480_444.mp4", (3289, 1480), (3289, 1480)),
    ("res_1080x1920_vertical.mp4", (1080, 1920), (1080, 1920)),
    ("anamorphic_720x576.mp4", (720, 576), (1024, 576)),
    ("rotated_90.mp4", (640, 360), (360, 640)),
])
def test_resolutions_are_detected_exactly(media_dir, name, size, display):
    info = probe_file(str(media_dir / name))
    assert info.ok, info.error
    assert (info.video.coded_width, info.video.coded_height) == size
    assert info.video.display_size == display


@needs_ffprobe
@pytest.mark.parametrize("label, fps", [
    ("24", Fraction(24)), ("23.976", Fraction(24000, 1001)), ("25", Fraction(25)), ("29.97", Fraction(30000, 1001)),
    ("30", Fraction(30)), ("50", Fraction(50)), ("59.94", Fraction(60000, 1001)), ("60", Fraction(60)),
])
def test_frame_rates_including_fractional(media_dir, label, fps):
    assert probe_file(str(media_dir / f"fps_{label}.mp4")).video.fps == fps


@needs_ffprobe
def test_audio_characteristics(media_dir):
    stereo = probe_file(str(media_dir / "audio_stereo_48k.mp4")).primary_audio
    assert (stereo.codec, stereo.channels, stereo.sample_rate) == ("aac", 2, 48000)
    surround = probe_file(str(media_dir / "audio_51.mp4")).primary_audio
    assert surround.channels == 6
    pcm = probe_file(str(media_dir / "audio_pcm24_96k.mov")).primary_audio
    assert (pcm.sample_rate, pcm.bit_depth) == (96000, 24)
    assert probe_file(str(media_dir / "res_1920x1080.mp4")).audio == []


@needs_ffprobe
def test_colour_metadata(media_dir):
    hdr = probe_file(str(media_dir / "hdr10_hevc.mp4")).video
    assert hdr.codec == "hevc" and hdr.bit_depth == 10 and hdr.hdr == "HDR10 (PQ)"
    full = probe_file(str(media_dir / "bt709_full_range.mp4")).video
    assert full.color_range == "pc"
    prores = probe_file(str(media_dir / "prores_1080.mov")).video
    assert prores.codec == "prores" and prores.chroma == "4:2:2"


@needs_ffprobe
def test_missing_metadata_and_broken_files(media_dir, fixtures_dir):
    raw = probe_file(str(media_dir / "no_metadata.h264"))
    assert raw.video is not None and raw.duration_ms is None and raw.video.bit_rate is None
    corrupt = probe_file(str(fixtures_dir / "corrupt.mp4"))
    assert not corrupt.ok and corrupt.error
    assert assess_media(corrupt, decode_ok=False).verdict is Verdict.UNSUPPORTED
    unknown = probe_file(str(media_dir / "unknown_codec.mp4"))
    assert assess_media(unknown).verdict is Verdict.UNSUPPORTED


def probe_all(qtbot, paths):
    service = ThumbnailService()
    results = {}
    service.probed.connect(lambda r: results.__setitem__(r.path, r))
    for p in paths:
        service.request(str(p))
    qtbot.waitUntil(lambda: len(results) == len(paths), timeout=60000)
    return results


def test_real_decode_by_the_playback_engine(qtbot, media_dir, fixtures_dir):
    good = ["res_3840x2160.mp4", "res_3289x1480_444.mp4", "res_1080x1920_vertical.mp4", "hdr10_hevc.mp4",
            "prores_1080.mov", "audio_51.mp4", "audio_pcm24_96k.mov", "fps_59.94.mp4", "rotated_90.mp4"]
    paths = [media_dir / n for n in good] + [media_dir / "unknown_codec.mp4", fixtures_dir / "corrupt.mp4"]
    results = probe_all(qtbot, paths)
    for n in good:
        r = results[str(media_dir / n)]
        assert r.ok, f"{n} : {r.error}"
        assert r.qt_meta.get("resolution"), n
    assert not results[str(media_dir / "unknown_codec.mp4")].ok
    assert not results[str(fixtures_dir / "corrupt.mp4")].ok
    w, h = results[str(media_dir / "res_3289x1480_444.mp4")].qt_meta["resolution"]
    assert (w, h) == (3289, 1480)


def test_very_large_file_is_never_loaded_in_memory(qtbot, media_dir, tmp_path):
    """Fichier de plus de 2 Go (fichier creux) : analyse et lecture sans tout lire."""
    big = tmp_path / "gros_fichier.mp4"
    shutil.copy(media_dir / "res_1920x1080.mp4", big)
    with open(big, "r+b") as fh:
        fh.truncate(2_300_000_000)
    assert os.path.getsize(big) > 2**31
    if find_ffprobe():
        t = time.monotonic()
        info = probe_file(str(big))
        assert info.ok and info.video.coded_width == 1920
        assert info.size_bytes > 2**31
        assert time.monotonic() - t < 15
    engine = QtPlaybackEngine(with_audio=False)
    started = []
    engine.started.connect(started.append)
    engine.load(str(big), 1)
    engine.play()
    qtbot.waitUntil(lambda: bool(started), timeout=20000)
    engine.stop()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg indisponible pour générer le fichier")
def test_high_bitrate_file_plays_in_real_time(qtbot, tmp_path):
    path = tmp_path / "haut_debit.mov"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=size=1920x1080:rate=25,noise=alls=60:allf=t", "-t", "2", "-c:v", "mjpeg", "-q:v", "1",
                    str(path)], check=True)
    if find_ffprobe():
        rate = probe_file(str(path)).video.bit_rate
        assert rate and rate > 50_000_000
    engine = QtPlaybackEngine(with_audio=False)
    ended = []
    engine.ended.connect(ended.append)
    engine.load(str(path), 1)
    engine.play()
    qtbot.waitUntil(lambda: bool(ended), timeout=30000)
    report = engine.telemetry.report()
    assert report.frames > 0
    assert report.realtime_ratio is None or report.realtime_ratio > 0.5


def test_telemetry_on_real_playback(qtbot, media_dir):
    engine = QtPlaybackEngine(with_audio=False)
    ended = []
    engine.ended.connect(ended.append)
    engine.load(str(media_dir / "fps_50.mp4"), 1)
    engine.play()
    qtbot.waitUntil(lambda: bool(ended), timeout=15000)
    r = engine.telemetry.report()
    assert r.frames >= 15 and r.startup_ms is not None
    assert engine.telemetry.fps == pytest.approx(50, rel=0.01)

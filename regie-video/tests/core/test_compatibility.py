"""Règles du diagnostic de compatibilité et de performances."""

from fractions import Fraction

import pytest

from app.media.compatibility import Severity, Verdict, assess_media, cadence_analysis
from app.media.media_info import AudioStreamInfo, MediaInfo, VideoStreamInfo
from app.media.telemetry import PlaybackReport


def media(codec="h264", w=1920, h=1080, fps=Fraction(25), bit_rate=10_000_000, profile="High", depth=8,
          chroma="4:2:0", space="bt709", transfer="bt709", rng="tv", audio=True, **extra) -> MediaInfo:
    v = VideoStreamInfo(codec=codec, profile=profile, coded_width=w, coded_height=h, fps=fps, r_fps=fps,
                        bit_rate=bit_rate, bit_depth=depth, chroma=chroma, color_space=space,
                        color_transfer=transfer, color_range=rng, **extra)
    info = MediaInfo(path="m.mp4", source="ffprobe", ok=True, video=v, video_stream_count=1, duration_ms=60000)
    if audio:
        info.audio.append(AudioStreamInfo(codec="aac", sample_rate=48000, channels=2))
    return info


def test_standard_hd_file_is_verified_after_real_decode():
    a = assess_media(media(), decode_ok=True, display_size=(1920, 1080), refresh_hz=50)
    assert a.verdict is Verdict.VERIFIED
    assert assess_media(media(), decode_ok=None).verdict is Verdict.PRESUMED  # pas encore décodé


def test_mp4_extension_is_not_enough():
    info = media(codec=None)
    assert assess_media(info, decode_ok=None).verdict is Verdict.UNSUPPORTED


def test_decode_failure_is_unsupported():
    a = assess_media(media(), decode_ok=False, decode_error="codec non pris en charge")
    assert a.verdict is Verdict.UNSUPPORTED
    assert "codec non pris en charge" in a.messages(Severity.BLOCKING)[0]


def test_analysis_impossible():
    assert assess_media(None).verdict is Verdict.UNKNOWN
    failed = MediaInfo(path="x", error="délai dépassé")
    assert assess_media(failed).verdict is Verdict.UNKNOWN
    assert assess_media(failed, decode_ok=True).verdict is Verdict.PRESUMED


def test_uhd30_h264_is_fine_but_uhd60_is_a_risk():
    assert assess_media(media(w=3840, h=2160, fps=Fraction(30)), decode_ok=True).verdict is Verdict.VERIFIED
    assert assess_media(media(w=3840, h=2160, fps=Fraction(60)), decode_ok=True).verdict is Verdict.PERF_RISK


def test_odd_resolution_444_h264_is_a_performance_risk():
    a = assess_media(media(w=3289, h=1480, profile="High 4:4:4 Predictive", chroma="4:4:4"), decode_ok=True)
    assert a.verdict is Verdict.PERF_RISK
    text = " ".join(a.messages())
    assert "4:4:4" in text and "impaires" in text


def test_beyond_hardware_decoder_limits():
    a = assess_media(media(w=5120, h=2160, fps=Fraction(25)), decode_ok=True)
    assert a.verdict is Verdict.PERF_RISK and "limites usuelles" in " ".join(a.messages())


def test_production_codecs_and_bitrate():
    prores = media(codec="prores", profile="HQ", depth=10, chroma="4:2:2", bit_rate=180_000_000)
    assert assess_media(prores, decode_ok=True).verdict is Verdict.PERF_RISK
    heavy = media(bit_rate=300_000_000)
    assert assess_media(heavy, decode_ok=True).verdict is Verdict.PERF_RISK
    high = media(bit_rate=120_000_000)
    a = assess_media(high, decode_ok=True)
    assert a.verdict is Verdict.PRESUMED and "SSD" in " ".join(a.messages())


def test_hdr_needs_check_and_is_blocking_in_cpu_renderer():
    hdr = media(codec="hevc", profile="Main 10", depth=10, space="bt2020nc", transfer="smpte2084")
    assert assess_media(hdr, decode_ok=True).verdict is Verdict.PRESUMED
    assert assess_media(hdr, decode_ok=True, renderer="cpu").verdict is Verdict.UNSUPPORTED


def test_measured_color_limitations():
    bt601 = media(space="smpte170m")
    assert "BT.601" in " ".join(assess_media(bt601, decode_ok=True).messages())
    assert assess_media(bt601, decode_ok=True, renderer="cpu").verdict is Verdict.VERIFIED
    full = media(rng="pc")
    assert assess_media(full, decode_ok=True).verdict is Verdict.VERIFIED
    assert assess_media(full, decode_ok=True, renderer="cpu").verdict is Verdict.PRESUMED


def test_interlaced_vfr_and_unknown_codec_need_a_test():
    assert assess_media(media(field_order="tt"), decode_ok=True).verdict is Verdict.PRESUMED
    vfr = media()
    vfr.video.r_fps = Fraction(60)
    vfr.video.fps = Fraction(2997, 100)
    assert assess_media(vfr, decode_ok=True).verdict is Verdict.PRESUMED
    assert assess_media(media(codec="weirdcodec"), decode_ok=True).verdict is Verdict.PRESUMED


def test_display_scaling_information():
    a = assess_media(media(w=3289, h=1480, chroma="4:2:0"), decode_ok=True, display_size=(1920, 1080))
    assert any("réduit à 58 %" in m for m in a.messages(Severity.INFO))
    small = assess_media(media(w=640, h=360), decode_ok=True, display_size=(1920, 1080))
    assert any("agrandi ×3" in m for m in small.messages(Severity.INFO))


def test_audio_downmix_and_resampling_do_not_change_media_verdict():
    info = media()
    info.audio[0] = AudioStreamInfo(codec="eac3", sample_rate=44100, channels=6)
    a = assess_media(info, decode_ok=True, audio_channels_max=2, audio_sample_rate=48000)
    assert a.verdict is Verdict.VERIFIED
    text = " ".join(a.messages())
    assert "downmix" in text and "rééchantillonnage" in text


def test_playback_report_drives_verdict():
    bad = PlaybackReport(frames=200, missing_frames=30, realtime_ratio=0.9)
    assert assess_media(media(), decode_ok=True, playback=bad).verdict is Verdict.PERF_RISK
    good = PlaybackReport(frames=250, missing_frames=0, realtime_ratio=1.0)
    a = assess_media(media(), decode_ok=True, playback=good)
    assert a.verdict is Verdict.VERIFIED and "réussi" in " ".join(a.messages())
    nothing = PlaybackReport()
    assert assess_media(media(), decode_ok=True, playback=nothing).verdict is Verdict.UNSUPPORTED


@pytest.mark.parametrize("fps, hz, regular", [
    (Fraction(25), 50, True), (Fraction(25), 100, True), (Fraction(30), 60, True), (Fraction(60), 60, True),
    (Fraction(24), 24, True), (Fraction(50), 50, True),
    (Fraction(25), 60, False), (Fraction(24), 60, False), (Fraction(24000, 1001), 60, False),
    (Fraction(30000, 1001), 60, False), (Fraction(60000, 1001), 60, False), (Fraction(60), 50, False),
])
def test_cadence_against_refresh(fps, hz, regular):
    severity, message = cadence_analysis(fps, hz)
    assert (severity is Severity.INFO) is regular, message


def test_cadence_hints_and_unknown_refresh():
    _sev, msg = cadence_analysis(Fraction(25), 60)
    assert "50 Hz" in msg or "25 Hz" in msg
    _sev, msg = cadence_analysis(Fraction(60000, 1001), 60)
    assert "environ toutes les" in msg
    assert cadence_analysis(Fraction(25), None) is None
    assert cadence_analysis(None, 60) is None

"""Télémétrie de lecture et bilan du diagnostic avant spectacle."""

from app.media.compatibility import Assessment, Finding, Severity, Verdict
from app.media.diagnostic import Level, Overall, build_report
from app.media.system_info import AudioOutputInfo, DisplayInfo, SystemInfo
from app.media.telemetry import FrameTelemetry, PlaybackReport
from app.models import Cue, EndBehavior, Show


def feed_regular(t: FrameTelemetry, n: int, fps: float, skip=(), start=10.0):
    period = 1 / fps
    for i in range(n):
        if i in skip:
            continue
        t.feed(start + i * period, int(i * period * 1_000_000))


def test_regular_playback_has_no_missing_frames():
    t = FrameTelemetry(fps=25)
    t.reset(launched_at=9.95)
    feed_regular(t, 100, 25)
    r = t.report()
    assert r.frames == 100 and r.missing_frames == 0
    assert round(r.startup_ms) == 50
    assert abs(r.realtime_ratio - 1) < 0.01
    assert round(r.max_gap_ms) == 40


def test_skipped_frames_are_counted_from_timestamps():
    t = FrameTelemetry(fps=50)
    t.reset()
    feed_regular(t, 100, 50, skip={10, 11, 12, 50})
    r = t.report()
    assert r.missing_frames == 4
    assert r.missing_ratio == 4 / 100
    assert "4 sautées" in r.summary_fr()


def test_pause_is_not_counted_as_a_gap():
    t = FrameTelemetry(fps=25)
    t.reset()
    feed_regular(t, 10, 25)
    t.interrupt()
    feed_regular(t, 10, 25, start=100.0)
    r = t.report()
    assert r.max_gap_ms < 50 and r.missing_frames == 0


def system(audio=True, displays=1) -> SystemInfo:
    d = DisplayInfo("Projecteur", 1920, 1080, 1.0, 60.0, True)
    out = AudioOutputInfo("hdmi", "HDMI", True, 48000, 2, 8, "32 bits flottant") if audio else None
    return SystemInfo(displays=[d] * displays, projection=d, audio_outputs=[out] if out else [], audio_output=out,
                      ffprobe_path="/usr/bin/ffprobe", ffprobe_version="7.1", cpu_count=8, os_name="Windows 11",
                      qt_version="Qt 6.12")


def make_show(tmp_path, n=2):
    cues = []
    for i in range(n):
        f = tmp_path / f"v{i}.mp4"
        f.write_bytes(b"x")
        cues.append(Cue(name=f"A{i}", video_path=str(f), end_behavior=EndBehavior.BLACK))
    return Show(name="S", cues=cues)


def test_ready_only_with_playback_test(tmp_path):
    show = make_show(tmp_path)
    verified = {c.id: Assessment(Verdict.VERIFIED, []) for c in show.cues}
    without = build_report(show, verified, system(), "Accéléré")
    assert without.overall is Overall.CHECK
    assert any("Fluidité non mesurée" in i.title for i in without.items)
    runs = {c.id: [PlaybackReport(frames=100, realtime_ratio=1.0)] for c in show.cues}
    ready = build_report(show, verified, system(), "Accéléré", playback=runs)
    assert ready.overall is Overall.READY
    assert "Prêt pour le spectacle" in ready.to_text("S")


def test_blocking_problems(tmp_path):
    show = make_show(tmp_path)
    show.cues[1].video_path = str(tmp_path / "absente.mp4")
    report = build_report(show, {show.cues[0].id: Assessment(Verdict.VERIFIED)}, system(), "Accéléré")
    assert report.overall is Overall.BLOCKING
    assert any(i.level is Level.BLOCKING and "introuvable" in i.title for i in report.items)


def test_missing_audio_output_blocks_only_when_media_has_sound(tmp_path):
    show = make_show(tmp_path, 1)
    ok = {show.cues[0].id: Assessment(Verdict.VERIFIED)}
    with_sound = build_report(show, ok, system(audio=False), "Accéléré", media_has_audio={show.cues[0].id: True})
    assert with_sound.overall is Overall.BLOCKING
    silent = build_report(show, ok, system(audio=False), "Accéléré", media_has_audio={show.cues[0].id: False})
    assert silent.overall is Overall.CHECK


def test_perf_risk_and_renderer_fallback_need_hardware_check(tmp_path):
    show = make_show(tmp_path, 1)
    risk = {show.cues[0].id: Assessment(Verdict.PERF_RISK, [Finding(Severity.PERF, "4K60")])}
    runs = {show.cues[0].id: [PlaybackReport(frames=10, realtime_ratio=1.0)]}
    assert build_report(show, risk, system(), "Accéléré", playback=runs).overall is Overall.CHECK
    ok = {show.cues[0].id: Assessment(Verdict.VERIFIED)}
    fallback = build_report(show, ok, system(), "Compatibilité", "pilote absent", playback=runs)
    assert fallback.overall is Overall.CHECK


def test_cadence_notes_are_grouped_once(tmp_path):
    show = make_show(tmp_path, 3)
    note = Finding(Severity.WARNING, "Cadence 25 i/s sur écran 60 Hz : rythme irrégulier", affects_verdict=False)
    a = {c.id: Assessment(Verdict.VERIFIED, [note]) for c in show.cues}
    report = build_report(show, a, system(), "Accéléré")
    assert sum("Cadence 25" in i.title for i in report.items) == 1

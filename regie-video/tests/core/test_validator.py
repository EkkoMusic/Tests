from app.media.media_validator import Severity, missing_file_count, validate_show
from app.models import Cue, EndBehavior, Show


def test_empty_show_is_an_error():
    issues = validate_show(Show())
    assert issues[0].severity is Severity.ERROR


def test_missing_video_and_image(tmp_path):
    video = tmp_path / "ok.mp4"; video.write_bytes(b"x")
    empty = tmp_path / "vide.mp4"; empty.write_bytes(b"")
    show = Show(cues=[
        Cue(name="OK", video_path=str(video), image_path=str(tmp_path / "absente.png")),
        Cue(name="Manquante", video_path=str(tmp_path / "absente.mp4"), end_behavior=EndBehavior.BLACK),
        Cue(name="Vide", video_path=str(empty), end_behavior=EndBehavior.BLACK),
    ])
    issues = validate_show(show)
    errors = [i for i in issues if i.severity is Severity.ERROR]
    warnings = [i for i in issues if i.severity is Severity.WARNING]
    assert [i.cue_index for i in errors] == [1, 2]
    assert "introuvable" in errors[0].message
    assert warnings[0].cue_index == 0 and "noir" in warnings[0].message
    assert missing_file_count(show) == 2


def test_probe_errors_are_reported(tmp_path):
    video = tmp_path / "x.mp4"; video.write_bytes(b"x")
    show = Show(cues=[Cue(name="X", video_path=str(video), end_behavior=EndBehavior.BLACK)])
    issues = validate_show(show, {str(video): "codec non pris en charge"})
    assert issues[0].severity is Severity.ERROR and "codec" in issues[0].message

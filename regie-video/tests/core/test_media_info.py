"""Lecture des caractéristiques (sortie JSON de FFprobe) et formatage en français."""

from fractions import Fraction

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
    media_info_from_qt,
    parse_ffprobe,
    probe_file,
)

HDR_51 = {
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "format_long_name": "QuickTime / MOV",
               "duration": "125.480000", "size": "4294967296", "bit_rate": "273000000"},
    "streams": [
        {"codec_type": "video", "codec_name": "hevc", "codec_long_name": "H.265 / HEVC", "profile": "Main 10",
         "width": 3289, "height": 1480, "sample_aspect_ratio": "1:1", "pix_fmt": "yuv420p10le",
         "color_range": "tv", "color_space": "bt2020nc", "color_transfer": "smpte2084", "color_primaries": "bt2020",
         "field_order": "progressive", "r_frame_rate": "24000/1001", "avg_frame_rate": "24000/1001",
         "bit_rate": "268000000", "nb_frames": "3008", "level": 153},
        {"codec_type": "audio", "codec_name": "eac3", "sample_rate": "48000", "channels": 6,
         "channel_layout": "5.1(side)", "bit_rate": "640000", "sample_fmt": "fltp"},
        {"codec_type": "audio", "codec_name": "aac", "sample_rate": "44100", "channels": 2, "channel_layout": "stereo"},
    ],
}


def test_full_parse_of_hdr_odd_resolution_file():
    info = parse_ffprobe(HDR_51, "film.mov")
    v = info.video
    assert info.ok and info.source == "ffprobe"
    assert (v.coded_width, v.coded_height) == (3289, 1480)
    assert v.display_size == (3289, 1480)
    assert v.fps == Fraction(24000, 1001)
    assert v.bit_depth == 10 and v.chroma == "4:2:0"
    assert v.hdr == "HDR10 (PQ)"
    assert info.duration_ms == 125480
    assert info.size_bytes == 4294967296
    assert len(info.audio) == 2
    a = info.primary_audio
    assert (a.codec, a.sample_rate, a.channels) == ("eac3", 48000, 6)
    assert format_channels(a) == "5.1 (6 canaux)"
    assert format_aspect(*v.display_size) == "2,22:1"
    assert format_fps(v.fps) == "23,976 i/s (24000/1001)"
    assert format_colors(v) == "BT.2020 · HDR10 (PQ) · plage limitée · 10 bits · 4:2:0"
    assert format_bitrate(v.bit_rate) == "268 Mbit/s"
    assert format_size(info.size_bytes) == "4 Go"


def test_missing_fields_stay_unknown():
    data = {"format": {}, "streams": [{"codec_type": "video", "codec_name": "h264", "width": 640, "height": 360,
                                        "r_frame_rate": "0/0", "avg_frame_rate": "0/0", "color_space": "unknown"}]}
    info = parse_ffprobe(data, "x.h264")
    v = info.video
    assert v.fps is None and v.bit_rate is None and info.duration_ms is None
    assert v.color_space is None and v.hdr is None
    assert info.audio == []
    assert format_fps(v.fps) is None and format_bitrate(None) is None


def test_rotation_and_anamorphic_pixels():
    rot = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
                        "side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90}]}]}
    assert parse_ffprobe(rot, "r.mp4").video.display_size == (1080, 1920)
    assert parse_ffprobe(rot, "r.mp4").video.rotation == 90
    legacy = {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
                           "tags": {"rotate": "270"}}]}
    assert parse_ffprobe(legacy, "r.mp4").video.display_size == (1080, 1920)
    sar = {"streams": [{"codec_type": "video", "codec_name": "mpeg2video", "width": 720, "height": 576,
                        "sample_aspect_ratio": "64:45"}]}
    assert parse_ffprobe(sar, "a.mpg").video.display_size == (1024, 576)


def test_variable_frame_rate_interlacing_and_tag_bitrate():
    data = {"format": {"bit_rate": "9000000"}, "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "r_frame_rate": "60/1",
         "avg_frame_rate": "2997/100", "field_order": "tt", "tags": {"BPS": "8500000"}},
    ]}
    v = parse_ffprobe(data, "v.mkv").video
    assert v.variable_frame_rate and v.is_interlaced
    assert v.bit_rate == 8_500_000


def test_bitrate_estimated_from_container():
    data = {"format": {"bit_rate": "10000000"}, "streams": [
        {"codec_type": "video", "codec_name": "prores", "width": 1920, "height": 1080},
        {"codec_type": "audio", "codec_name": "pcm_s24le", "bit_rate": "2304000", "sample_rate": "48000", "channels": 2,
         "bits_per_sample": 24},
    ]}
    info = parse_ffprobe(data, "p.mov")
    assert info.video_bit_rate_estimated and info.video.bit_rate == 10_000_000 - 2_304_000
    assert info.primary_audio.bit_depth == 24
    assert codec_label("pcm_s24le") == "PCM non compressé (s24le)"


def test_cover_art_is_not_the_video_and_no_video_is_reported():
    data = {"streams": [{"codec_type": "audio", "codec_name": "mp3"},
                        {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}}]}
    info = parse_ffprobe(data, "song.mp3")
    assert info.video is None and info.video_stream_count == 0


def test_probe_missing_file_does_not_raise(tmp_path):
    info = probe_file(str(tmp_path / "absent.mp4"))
    assert not info.ok and "inaccessible" in info.error


def test_probe_without_ffprobe(tmp_path, monkeypatch):
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    monkeypatch.setenv("REGIE_VIDEO_FFPROBE", str(tmp_path / "nope.exe"))
    info = probe_file(str(f))
    assert not info.ok and "FFprobe" in info.error


def test_qt_fallback():
    info = media_info_from_qt("x.mp4", {"resolution": (3289, 1480), "fps": 23.976023976, "video_codec": "h264",
                                        "duration_ms": 5000, "has_audio": True, "audio_codec": "aac"})
    assert info.partial and info.video.fps == Fraction(24000, 1001)
    assert info.video.display_size == (3289, 1480)
    assert info.primary_audio.codec == "aac" and info.primary_audio.channels is None
    empty = media_info_from_qt("y.mp4", {})
    assert not empty.ok


def test_french_formatting():
    assert format_aspect(1920, 1080) == "16:9 (1,78:1)"
    assert format_aspect(3840, 2160) == "16:9 (1,78:1)"
    assert format_aspect(1080, 1920) == "9:16 (vertical)"
    assert format_aspect(1024, 1024) == "1:1"
    assert format_aspect(1000, 2000) == "1:2 (vertical)"
    assert format_fps(Fraction(25)) == "25 i/s"
    assert format_fps(Fraction(30000, 1001)) == "29,97 i/s (30000/1001)"
    assert format_fps(Fraction(60000, 1001)) == "59,94 i/s (60000/1001)"
    assert format_bitrate(850_000) == "850 kbit/s"
    assert format_bitrate(43_562_110) == "43,6 Mbit/s"
    assert format_size(27_227_844) == "26 Mo"
    assert format_sample_rate(44100) == "44,1 kHz" and format_sample_rate(96000) == "96 kHz"
    assert codec_label("hevc", "Main 10") == "H.265 / HEVC · Main 10"
    assert codec_label(None) is None

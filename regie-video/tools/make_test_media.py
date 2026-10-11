"""Génère les médias de test de tests/fixtures/media (FFmpeg avec libx264/libx265 requis).

Les fichiers sont volontairement minuscules (fractions de seconde, forte
compression) : ils servent à vérifier la détection des caractéristiques et
le comportement du moteur, pas la qualité d'image.

    python tools/make_test_media.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "media"
FF = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]


def run(args: list[str], name: str) -> None:
    subprocess.run(FF + args + [str(OUT / name)], check=True)
    print(f"{name:32s} {(OUT / name).stat().st_size / 1024:8.1f} ko")


def video(size: str, rate: str, seconds: float, extra: list[str], name: str, audio: list[str] | None = None) -> None:
    args = ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}"]
    if audio:
        args += audio
    args += ["-t", str(seconds)] + extra
    if audio:
        args += ["-shortest"]
    run(args + ["-movflags", "+faststart"], name)


H264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "42", "-pix_fmt", "yuv420p"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Résolutions
    video("1920x1080", "25", 0.4, H264, "res_1920x1080.mp4")
    video("3840x2160", "30", 0.3, H264, "res_3840x2160.mp4")
    # 3289 px : largeur impaire, impossible en H.264 4:2:0 → H.264 4:4:4 (High 4:4:4).
    video("3290x1480", "25", 0.3, ["-vf", "format=yuv444p,crop=3289:1480:0:0", "-c:v", "libx264", "-preset", "veryfast",
                                   "-crf", "42", "-pix_fmt", "yuv444p"], "res_3289x1480_444.mp4")
    video("1080x1920", "25", 0.4, H264, "res_1080x1920_vertical.mp4")
    # Cadences
    for rate, label in (("24", "24"), ("24000/1001", "23.976"), ("25", "25"), ("30000/1001", "29.97"), ("30", "30"),
                        ("50", "50"), ("60000/1001", "59.94"), ("60", "60")):
        video("160x90", rate, 0.4, H264, f"fps_{label}.mp4")
    # Audio
    video("320x180", "25", 0.5, H264 + ["-c:a", "aac", "-b:a", "128k"], "audio_stereo_48k.mp4",
          ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-ac", "2"])
    video("320x180", "25", 0.5, H264 + ["-c:a", "aac", "-b:a", "256k", "-ac", "6"], "audio_51.mp4",
          ["-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000"])
    video("320x180", "25", 0.2, H264 + ["-c:a", "pcm_s24le"], "audio_pcm24_96k.mov",
          ["-f", "lavfi", "-i", "sine=frequency=550:sample_rate=96000", "-ac", "2"])
    # HDR10 (HEVC 10 bits, PQ, BT.2020)
    video("320x180", "25", 0.4, ["-c:v", "libx265", "-preset", "ultrafast", "-crf", "40", "-pix_fmt", "yuv420p10le",
                                  "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc",
                                  "-color_range", "tv", "-tag:v", "hvc1", "-x265-params", "log-level=error"], "hdr10_hevc.mp4")
    # BT.709 plage complète
    video("320x180", "25", 0.4, ["-c:v", "libx264", "-preset", "veryfast", "-crf", "40", "-pix_fmt", "yuvj420p",
                                  "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                                  "-color_range", "pc"], "bt709_full_range.mp4")
    # Pixels non carrés et rotation
    video("720x576", "25", 0.4, H264 + ["-vf", "setsar=64/45"], "anamorphic_720x576.mp4")
    src = OUT / "_tmp_rot.mp4"
    subprocess.run(FF + ["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25", "-t", "0.4"] + H264 + [str(src)], check=True)
    run(["-display_rotation", "90", "-i", str(src), "-c", "copy"], "rotated_90.mp4")
    src.unlink()
    # ProRes (codec de production, décodé par le processeur)
    video("1920x1080", "25", 0.08, ["-c:v", "prores_ks", "-profile:v", "0", "-pix_fmt", "yuv422p10le"], "prores_1080.mov")
    # Codec inconnu : code « avc1 » remplacé dans l'en-tête du conteneur.
    data = (OUT / "fps_25.mp4").read_bytes().replace(b"avc1", b"zzz9")
    (OUT / "unknown_codec.mp4").write_bytes(data)
    print(f"{'unknown_codec.mp4':32s} {len(data) / 1024:8.1f} ko")
    # Flux H.264 brut : pas de conteneur, donc ni durée ni débit.
    subprocess.run(FF + ["-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25", "-t", "0.4"] + H264
                   + ["-f", "h264", str(OUT / "no_metadata.h264")], check=True)
    print("no_metadata.h264")


if __name__ == "__main__":
    sys.exit(main())

"""Diagnostic de compatibilité et de performances d'un média.

Le verdict ne repose jamais sur la seule extension du fichier : il combine
les caractéristiques lues (codec, profil, résolution, cadence, débit…), le
résultat d'un décodage réel par le moteur de lecture, l'éventuel test de
lecture, et les capacités du système (écran, sortie audio).

Les règles de performances sont des estimations prudentes, fondées sur les
limites usuelles des décodeurs matériels des PC Windows ; elles signalent un
risque, elles ne le prouvent pas. Seul le test sur le matériel réel le peut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction

from .media_info import MediaInfo, codec_label, format_bitrate, format_fps, fr_number
from .telemetry import PlaybackReport


class Verdict(str, Enum):
    VERIFIED = "verified"
    PRESUMED = "presumed"
    PERF_RISK = "perf_risk"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {
            Verdict.VERIFIED: "Compatible et vérifié",
            Verdict.PRESUMED: "Compatible présumé, test nécessaire",
            Verdict.PERF_RISK: "Risque de performances",
            Verdict.UNSUPPORTED: "Média non pris en charge",
            Verdict.UNKNOWN: "Analyse impossible",
        }[self]

    @property
    def short(self) -> str:
        return {
            Verdict.VERIFIED: "Prête",
            Verdict.PRESUMED: "À tester",
            Verdict.PERF_RISK: "Risque perf.",
            Verdict.UNSUPPORTED: "Non prise en charge",
            Verdict.UNKNOWN: "Analyse impossible",
        }[self]

    @property
    def kind(self) -> str:
        return {
            Verdict.VERIFIED: "success",
            Verdict.PRESUMED: "accent",
            Verdict.PERF_RISK: "warning",
            Verdict.UNSUPPORTED: "error",
            Verdict.UNKNOWN: "warning",
        }[self]


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    PERF = "perf"
    BLOCKING = "blocking"


@dataclass
class Finding:
    severity: Severity
    message: str
    # False : remarque sur la configuration d'affichage, pas sur le média lui-même.
    affects_verdict: bool = True


@dataclass
class Assessment:
    verdict: Verdict
    findings: list[Finding] = field(default_factory=list)

    def messages(self, *severities: Severity) -> list[str]:
        return [f.message for f in self.findings if not severities or f.severity in severities]


# Codecs que le moteur Qt Multimedia (FFmpeg) sait décoder.
KNOWN_DECODABLE = {
    "h264", "hevc", "av1", "vp9", "vp8", "mpeg2video", "mpeg1video", "mpeg4", "mjpeg", "prores", "dnxhd",
    "ffv1", "cfhd", "qtrle", "png", "hap", "theora", "wmv3", "vc1", "msmpeg4v3", "rawvideo", "utvideo",
}
# Codecs de production : décodés par le processeur (aucune accélération matérielle sous Windows).
SOFTWARE_ONLY = {"prores", "dnxhd", "ffv1", "cfhd", "qtrle", "mjpeg", "png", "hap", "rawvideo", "utvideo"}
# Limites usuelles des décodeurs matériels (D3D11VA / DXVA2).
HW_MAX = {"h264": (4096, 2304), "hevc": (8192, 4320), "vp9": (8192, 4352), "av1": (8192, 4352), "mpeg2video": (1920, 1088)}

UHD30 = 3840 * 2160 * 30
HIGH_BITRATE = 100_000_000
VERY_HIGH_BITRATE = 250_000_000


def cadence_analysis(fps: Fraction | float | None, refresh_hz: float | None) -> tuple[Severity, str] | None:
    """Rapport entre la cadence du média et la fréquence de l'écran."""
    if not fps or not refresh_hz or refresh_hz <= 0:
        return None
    fps = float(fps)
    ratio = refresh_hz / fps
    n = round(ratio)
    fps_txt = format_fps(Fraction(fps).limit_denominator(1001)) or f"{fr_number(fps)} i/s"
    hz_txt = f"{fr_number(refresh_hz)} Hz"
    if n >= 1 and abs(ratio - n) / ratio < 0.002:
        drift = abs(refresh_hz - fps * n)
        if drift < 1e-6 or 1 / drift > 600:
            return (Severity.INFO, f"Cadence {fps_txt} sur écran {hz_txt} : affichage régulier"
                    + (f" (chaque image affichée {n} fois)." if n > 1 else "."))
        period = 1 / drift
        return (Severity.WARNING, f"Cadence {fps_txt} sur écran {hz_txt} : une image répétée ou sautée "
                                  f"environ toutes les {fr_number(period, 0)} s (légère saccade possible).")
    if ratio < 1:
        return (Severity.WARNING, f"Cadence {fps_txt} supérieure à la fréquence de l'écran ({hz_txt}) : "
                                  "des images ne seront jamais affichées.")
    better = [hz for hz in (24, 25, 30, 48, 50, 60, 72, 100, 120) if abs(hz / fps - round(hz / fps)) / (hz / fps) < 0.002]
    hint = f" Si le projecteur le permet, réglez l'affichage sur {better[0]} Hz." if better else ""
    return (Severity.WARNING, f"Cadence {fps_txt} sur écran {hz_txt} : rythme irrégulier (cadence non multiple), "
                              f"saccades possibles sur les mouvements lents.{hint}")


def assess_media(
    info: MediaInfo | None,
    decode_ok: bool | None = None,
    decode_error: str = "",
    display_size: tuple[int, int] | None = None,
    refresh_hz: float | None = None,
    audio_channels_max: int | None = None,
    audio_sample_rate: int | None = None,
    playback: PlaybackReport | None = None,
    renderer: str = "gpu",
) -> Assessment:
    findings: list[Finding] = []

    def add(sev: Severity, msg: str, affects: bool = True) -> None:
        findings.append(Finding(sev, msg, affects))

    if decode_ok is False:
        add(Severity.BLOCKING, f"Le moteur de lecture ne parvient pas à décoder ce fichier ({decode_error or 'erreur inconnue'}).")
    if info is None or (not info.ok and info.video is None):
        if info is not None and info.error:
            add(Severity.WARNING if decode_ok is not False else Severity.BLOCKING, f"Analyse : {info.error}.")
        if decode_ok is False:
            return Assessment(Verdict.UNSUPPORTED, findings)
        if decode_ok is True:
            add(Severity.INFO, "Caractéristiques détaillées indisponibles, mais le décodage a été vérifié.")
            return Assessment(Verdict.PRESUMED, findings)
        return Assessment(Verdict.UNKNOWN, findings)

    v = info.video
    if v is None:
        add(Severity.BLOCKING, "Aucune piste vidéo dans ce fichier.")
        return Assessment(Verdict.UNSUPPORTED, findings)
    if not v.codec:
        add(Severity.BLOCKING, "Codec vidéo inconnu.")
    elif v.codec not in KNOWN_DECODABLE:
        add(Severity.WARNING, f"Codec peu courant ({codec_label(v.codec)}) : seule une lecture réelle peut confirmer sa prise en charge.")
    if info.partial:
        add(Severity.INFO, "Analyse partielle (FFprobe indisponible) : profil, couleurs et canaux audio non vérifiés.")

    # ------------------------------------------------------- performances
    w, h = v.coded_width or 0, v.coded_height or 0
    if v.pixel_rate and v.pixel_rate > UHD30 * 1.05:
        add(Severity.PERF, f"Charge de décodage très élevée ({w} × {h} à {format_fps(v.fps)}), au-delà de la 4K à 30 i/s.")
    hw = HW_MAX.get(v.codec or "")
    if hw and (w > hw[0] or h > hw[1]):
        add(Severity.PERF, f"{w} × {h} dépasse les limites usuelles du décodage matériel {codec_label(v.codec)} "
                           f"({hw[0]} × {hw[1]}) : décodage par le processeur probable.")
    if v.codec == "h264" and ((v.bit_depth or 8) > 8 or (v.chroma and v.chroma != "4:2:0")):
        add(Severity.PERF, f"H.264 {v.bit_depth or ''} bits {v.chroma or ''} ({v.profile or 'profil avancé'}) : "
                           "rarement accéléré par les cartes graphiques, décodage par le processeur probable.")
    if v.codec == "hevc" and v.chroma and v.chroma != "4:2:0":
        add(Severity.PERF, f"HEVC {v.chroma} : accélération matérielle limitée aux GPU récents.")
    if v.codec in SOFTWARE_ONLY and w * h >= 1920 * 1080:
        add(Severity.PERF, f"{codec_label(v.codec)} est décodé par le processeur (pas d'accélération matérielle sous Windows).")
    if v.codec == "av1":
        add(Severity.WARNING, "AV1 : accéléré uniquement par les cartes graphiques récentes ; à vérifier sur le PC de spectacle.")
    rate = v.bit_rate or info.overall_bit_rate
    if rate and rate > VERY_HIGH_BITRATE:
        add(Severity.PERF, f"Débit très élevé ({format_bitrate(rate)}) : lire impérativement depuis un SSD interne.")
    elif rate and rate > HIGH_BITRATE:
        add(Severity.WARNING, f"Débit élevé ({format_bitrate(rate)}) : préférer un SSD interne à une clé USB ou un disque réseau.")
    if v.fps and float(v.fps) > 61:
        add(Severity.PERF, f"Cadence élevée ({format_fps(v.fps)}).")

    # ------------------------------------------------------------ qualité
    if v.variable_frame_rate:
        add(Severity.WARNING, f"Cadence variable (moyenne {format_fps(v.fps)}, nominale {format_fps(v.r_fps)}) : "
                              "la fluidité doit être vérifiée.")
    if v.is_interlaced:
        add(Severity.WARNING, "Vidéo entrelacée : aucun désentrelacement n'est appliqué, effet de peigne possible.")
    if v.hdr:
        if renderer == "cpu":
            add(Severity.BLOCKING, f"Vidéo {v.hdr} : le rendu « Compatibilité » ne sait pas l'afficher "
                                   "(image noire mesurée). Utilisez le rendu accéléré.")
        else:
            add(Severity.WARNING, f"Vidéo {v.hdr} : convertie pour un affichage SDR par le moteur ; "
                                  "rendu des couleurs à vérifier sur le projecteur.")
    # Constats mesurés sur Qt Multimedia 6.12 (voir docs/NOTES_TECHNIQUES.md).
    if v.chroma in ("4:2:2", "4:4:4") or (v.chroma == "RVB"):
        add(Severity.WARNING, f"Couleurs en {v.chroma} : le moteur Qt Multimedia les convertit en 4:2:0 avant "
                              "l'affichage (définition des couleurs réduite de moitié, visible surtout sur les "
                              "textes et contours très colorés).")
    if v.color_space in ("bt470bg", "smpte170m") and renderer != "cpu":
        add(Severity.WARNING, "Fichier étiqueté BT.601 : le rendu accéléré de Qt applique la matrice BT.709 "
                              "(teintes légèrement décalées, mesuré). Préférez un export en BT.709, "
                              "ou le rendu « Compatibilité » si toutes les vidéos sont dans ce cas.")
    if renderer == "cpu" and (v.color_range == "pc" or (not v.color_space and (v.coded_height or 0) >= 720)):
        add(Severity.WARNING, "Le rendu « Compatibilité » interprète mal ce fichier (plage complète ou espace "
                              "colorimétrique non signalé) : couleurs décalées mesurées. Utilisez le rendu accéléré.")
    if w % 2 or h % 2:
        add(Severity.INFO, f"Dimensions impaires ({w} × {h}) : prises en charge, aucune action nécessaire.")
    if v.rotation:
        add(Severity.INFO, f"Rotation de {v.rotation}° indiquée dans le fichier : appliquée automatiquement.")
    if v.sar and v.sar != 1:
        add(Severity.INFO, f"Pixels non carrés ({v.sar.numerator}:{v.sar.denominator}) : proportions corrigées automatiquement.")
    size = v.display_size
    if size and display_size and display_size[0] and display_size[1]:
        dw, dh = display_size
        scale = min(dw / size[0], dh / size[1])
        if scale < 0.99:
            add(Severity.INFO, f"Le média ({size[0]} × {size[1]}) est plus grand que la sortie ({dw} × {dh}) : "
                               f"réduit à {fr_number(scale * 100, 0)} %, le projecteur ne peut pas afficher davantage de détails.")
        elif scale > 1.5:
            add(Severity.INFO, f"Le média ({size[0]} × {size[1]}) est agrandi ×{fr_number(scale, 1)} pour remplir la sortie ({dw} × {dh}).")
    cadence = cadence_analysis(v.fps, refresh_hz)
    if cadence:
        add(*cadence, affects=False)

    # --------------------------------------------------------------- audio
    a = info.primary_audio
    if a is not None:
        if audio_channels_max and a.channels and a.channels > audio_channels_max:
            add(Severity.WARNING, f"Audio {a.channels} canaux sur une sortie {audio_channels_max} canaux : "
                                  "mixage réduit (downmix) effectué par le système.", affects=False)
        if audio_sample_rate and a.sample_rate and a.sample_rate != audio_sample_rate:
            add(Severity.INFO, f"Audio à {fr_number(a.sample_rate / 1000, 1)} kHz, sortie réglée sur "
                               f"{fr_number(audio_sample_rate / 1000, 1)} kHz : rééchantillonnage par Windows ou Qt.",
                affects=False)
    if len(info.audio) > 1:
        add(Severity.INFO, f"{len(info.audio)} pistes audio : seule la première est lue.")

    # ------------------------------------------------------ test de lecture
    if playback is not None:
        if playback.frames == 0:
            add(Severity.BLOCKING, "Test de lecture : aucune image reçue.")
        elif playback.missing_ratio > 0.01 or (playback.realtime_ratio is not None and playback.realtime_ratio < 0.97):
            add(Severity.PERF, f"Test de lecture : {playback.summary_fr()}.")
        else:
            add(Severity.INFO, f"Test de lecture réussi : {playback.summary_fr()}.")

    severities = {f.severity for f in findings if f.affects_verdict}
    if Severity.BLOCKING in severities:
        verdict = Verdict.UNSUPPORTED
    elif Severity.PERF in severities:
        verdict = Verdict.PERF_RISK
    elif decode_ok is True and v.codec in KNOWN_DECODABLE and Severity.WARNING not in severities:
        verdict = Verdict.VERIFIED
    else:
        verdict = Verdict.PRESUMED
    return Assessment(verdict, findings)

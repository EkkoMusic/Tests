"""Génère assets/icons/regie-video.ico et logo.png à partir de logo.svg."""

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "assets" / "icons"


def render(size: int) -> QImage:
    renderer = QSvgRenderer(str(ICONS / "logo.svg"))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return image


def write_ico(path: Path, sizes=(16, 24, 32, 48, 64, 128, 256)) -> None:
    """ICO multi-résolution (images PNG embarquées, format accepté par Windows Vista+)."""
    import struct

    from PySide6.QtCore import QBuffer, QByteArray, QIODevice

    blobs = []
    for s in sizes:
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        render(s).save(buf, "PNG")
        blobs.append((s, bytes(data.data())))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries, payload = b"", b""
    for s, blob in blobs:
        dim = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset + len(payload))
        payload += blob
    path.write_bytes(header + entries + payload)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    render(512).save(str(ICONS / "logo.png"))
    write_ico(ICONS / "regie-video.ico")
    print("Icônes générées dans", ICONS)

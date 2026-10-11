# -*- mode: python ; coding: utf-8 -*-
# Spécification PyInstaller de Régie Vidéo — distribution « onedir ».
#   pyinstaller --noconfirm --clean RegieVideo.spec
# Résultat : dist/RegieVideo/RegieVideo.exe (+ bibliothèques Qt et FFmpeg à côté).
import sys

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=["PySide6.QtSvg", "PySide6.QtMultimedia"],
    excludes=["tkinter", "unittest", "pytest", "pytestqt"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RegieVideo",
    console=False,          # application fenêtrée : aucune console visible
    debug=False,
    strip=False,
    upx=False,              # UPX peut corrompre les DLL Qt/FFmpeg
    icon="assets/icons/regie-video.ico",
    version="packaging/version_info.txt" if sys.platform == "win32" else None,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RegieVideo")

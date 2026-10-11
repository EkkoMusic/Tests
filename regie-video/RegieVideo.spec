# -*- mode: python ; coding: utf-8 -*-
# Spécification PyInstaller de Régie Vidéo — distribution « onedir ».
#   pyinstaller --noconfirm --clean RegieVideo.spec
# Résultat : dist/RegieVideo/RegieVideo.exe (+ bibliothèques Qt et FFmpeg à côté).
import os
import sys

datas = [("assets", "assets")]
# FFprobe (diagnostic des médias) : placé par build_windows.bat ou la CI dans vendor/ffmpeg.
ffprobe = os.path.join("vendor", "ffmpeg", "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
if os.path.isfile(ffprobe):
    datas.append((ffprobe, "ffmpeg"))
    for extra in ("LICENSE.txt", "README.txt"):
        path = os.path.join("vendor", "ffmpeg", extra)
        if os.path.isfile(path):
            datas.append((path, "ffmpeg"))

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtSvg", "PySide6.QtMultimedia", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQml"],
    excludes=["tkinter", "unittest", "pytest", "pytestqt", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtPdf"],
    noarchive=False,
)

# Modules QML : seuls QtQuick (base), QtQml et QtMultimedia sont utilisés.
_KEEP_QML = ("QtQuick/qmldir", "QtQuick/plugins.qmltypes", "QtQml", "QtMultimedia", "QtQuick/Window")
_DROP_QML = ("QtQuick/Controls", "QtQuick/Dialogs", "QtQuick/Templates", "QtQuick/NativeStyle", "QtQuick/Pdf",
             "QtQuick/VirtualKeyboard", "QtQuick/Scene3D", "QtQuick/Timeline", "QtQuick3D", "QtWebEngine", "QtWebView",
             "QtCharts", "QtDataVisualization", "QtGraphs", "QtLocation", "QtPositioning", "Qt3D", "QtSensors",
             "QtTest", "QtRemoteObjects", "QtScxml", "QtTextToSpeech", "QtWebSockets", "QtWebChannel", "QtLottie")


def _keep(entry):
    dest = entry[0].replace("\\", "/")
    marker = "/qml/"
    if marker not in dest:
        return True
    rel = dest.split(marker, 1)[1]
    return not any(rel.startswith(d + "/") or rel == d for d in _DROP_QML)


# Bibliothèques Qt tirées par l'analyse mais inutiles à Régie Vidéo (WebEngine pèse à lui seul ~200 Mo).
_DROP_LIBS = ("WebEngine", "Quick3D", "QuickDialogs2", "QuickControls2", "QuickTemplates2", "QuickTimeline",
              "Qt6Pdf", "Charts", "DataVisualization", "Graphs", "Location", "Positioning", "Sensors",
              "VirtualKeyboard", "Qt63D", "Scxml", "TextToSpeech", "RemoteObjects", "Lottie", "Designer",
              "Qt6Help", "Bluetooth", "Nfc", "SerialPort", "SerialBus", "WebView", "WebSockets", "WebChannel",
              "ShaderTools", "Qt5Compat", "QuickParticles", "QuickShapes", "QuickTest", "Qt6Test")


def _keep_lib(entry):
    name = os.path.basename(entry[0].replace("\\", "/"))
    return _keep(entry) and not any(token in name for token in _DROP_LIBS)


a.datas = [d for d in a.datas if _keep(d) and "/qml/Qt5Compat" not in d[0].replace("\\", "/")]
a.binaries = [b for b in a.binaries if _keep_lib(b)]

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

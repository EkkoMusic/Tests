@echo off
rem ======================================================================
rem  Compilation de Régie Vidéo pour Windows (distribution « onedir »)
rem  Prérequis : Python 3.12 (64 bits) installé et accessible via « py ».
rem  Résultat  : dist\RegieVideo\RegieVideo.exe
rem ======================================================================
setlocal
chcp 65001 > nul
cd /d "%~dp0"

if not exist .venv (
    echo [1/5] Création de l'environnement Python...
    py -3.12 -m venv .venv || py -3 -m venv .venv || goto :erreur
)
call .venv\Scripts\activate.bat || goto :erreur

echo [2/5] Installation des dépendances...
python -m pip install --upgrade pip > nul
python -m pip install -r requirements-dev.txt || goto :erreur

echo [2b/5] FFprobe pour le diagnostic des médias...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\get_ffprobe.ps1 || goto :erreur
set PATH=%~dp0vendor\ffmpeg;%PATH%

echo [3/5] Tests automatisés...
set QT_QPA_PLATFORM=offscreen
python -m pytest -q || goto :erreur
set QT_QPA_PLATFORM=

echo [4/5] Compilation avec PyInstaller...
pyinstaller --noconfirm --clean RegieVideo.spec || goto :erreur

echo [5/5] Auto-test de l'exécutable (lecture vidéo, rendu GPU, FFprobe)...
dist\RegieVideo\RegieVideo.exe --self-test
if errorlevel 1 (
    echo L'auto-test a échoué : voir %%APPDATA%%\RegieVideo\logs\selftest.txt
    goto :erreur
)

echo.
echo Compilation terminée : dist\RegieVideo\RegieVideo.exe
echo Copiez tout le dossier dist\RegieVideo sur le PC de régie.
exit /b 0

:erreur
echo.
echo *** La compilation a échoué. ***
exit /b 1

@echo off
rem Lance Régie Vidéo depuis les sources (développement).
setlocal
cd /d "%~dp0"
if not exist .venv (
    py -3.12 -m venv .venv || py -3 -m venv .venv || exit /b 1
    call .venv\Scripts\activate.bat
    python -m pip install -r requirements-dev.txt || exit /b 1
) else (
    call .venv\Scripts\activate.bat
)
python main.py %*

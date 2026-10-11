#!/usr/bin/env sh
# Lance Régie Vidéo depuis les sources (macOS / Linux, développement).
cd "$(dirname "$0")" || exit 1
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt; } || exit 1
exec .venv/bin/python main.py "$@"

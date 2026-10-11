import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Affichage virtuel par défaut ; REGIE_VIDEO_QPA permet un vrai rendu (tests GPU).
os.environ.setdefault("QT_QPA_PLATFORM", os.environ.get("REGIE_VIDEO_QPA", "offscreen"))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("REGIE_VIDEO_DATA_DIR", str(tmp_path / "appdata"))


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES

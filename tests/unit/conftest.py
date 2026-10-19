import copy
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = REPO_ROOT / "examples" / "demo_house" / "project.json"
_DEMO = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
MODERN_PATH = REPO_ROOT / "examples" / "modern_townhouse" / "project.json"
_MODERN = json.loads(MODERN_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def demo_data() -> dict:
    return copy.deepcopy(_DEMO)


@pytest.fixture
def modern_data() -> dict:
    return copy.deepcopy(_MODERN)

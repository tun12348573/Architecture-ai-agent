import copy
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = REPO_ROOT / "examples" / "demo_house" / "project.json"
_DEMO = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
MODERN_PATH = REPO_ROOT / "examples" / "modern_townhouse" / "project.json"
_MODERN = json.loads(MODERN_PATH.read_text(encoding="utf-8"))
CLASSIC_PATH = REPO_ROOT / "examples" / "neoclassical_townhouse" / "project.json"
_CLASSIC = json.loads(CLASSIC_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def demo_data() -> dict:
    return copy.deepcopy(_DEMO)


@pytest.fixture
def modern_data() -> dict:
    return copy.deepcopy(_MODERN)


@pytest.fixture
def classic_data() -> dict:
    return copy.deepcopy(_CLASSIC)


def with_props(data: dict) -> dict:
    """Restore the M2a placeholders (car + 2 motorbikes); the demo dropped them in M2c."""
    yard = data["modern"]["front_yard"]
    yard["car"]["value"], yard["motorbikes"]["value"] = True, 2
    return data

import copy
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = REPO_ROOT / "examples" / "demo_house" / "project.json"
_DEMO = json.loads(DEMO_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def demo_data() -> dict:
    return copy.deepcopy(_DEMO)

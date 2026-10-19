import json
from pathlib import Path

import pytest

from exterior_agent.blender.invoke import (
    BlenderNotFound,
    blender_command,
    find_blender,
    run_blender,
)
from exterior_agent.domain.validate import load_project

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PATH = REPO_ROOT / "examples" / "demo_house" / "project.json"
TIMEOUT_S = 600


@pytest.fixture(scope="session")
def blender_cmd() -> list[str]:
    try:
        return find_blender()
    except BlenderNotFound as exc:
        pytest.skip(f"real Blender not configured: {exc}")


@pytest.fixture
def demo_project():
    return load_project(DEMO_PATH)


def run_script(blender: list[str], script: str, args: list[str], log: Path) -> list[str]:
    lines: list[str] = []
    result = run_blender(
        blender_command(blender, script, args), log, TIMEOUT_S, on_line=lines.append
    )
    assert result.status == "ok", log.read_text(encoding="utf-8")[-4000:]
    return lines


def inspect(
    blender: list[str],
    work: Path,
    *,
    blend: Path | None = None,
    glb: Path | None = None,
    rays: list[dict] | None = None,
) -> dict:
    out = work / f"inspect-{len(list(work.glob('inspect-*.json')))}.json"
    args = ["--blend", str(blend)] if blend else ["--glb", str(glb)]
    args += ["--out", str(out)]
    if rays is not None:
        rays_path = work / f"{out.stem}.rays"
        rays_path.write_text(json.dumps(rays), encoding="utf-8")
        args += ["--rays", str(rays_path)]
    run_script(blender, "inspect_scene.py", args, work / "inspect.log")
    return json.loads(out.read_text(encoding="utf-8"))

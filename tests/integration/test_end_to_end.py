import copy
import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from exterior_agent.blender.invoke import find_blender
from exterior_agent.domain.project import CANONICAL_CAMERA_IDS
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.runtime.delivery import validate_png, verify_delivery
from exterior_agent.runtime.files import sha256_file
from exterior_agent.runtime.runner import BuildOptions, run_build
from tests.integration.conftest import DEMO_PATH, inspect

pytestmark = pytest.mark.blender
SMOKE = resolve_render("smoke")
DEMO = json.loads(DEMO_PATH.read_text(encoding="utf-8"))


# Slow enough per view that a cancel lands before the remaining views finish.
SLOW = replace(SMOKE, width=640, height=360, samples=64)


def options(out, render=SMOKE, **kwargs) -> BuildOptions:
    return BuildOptions(out_dir=out, render=render, blender=find_blender(), **kwargs)


@pytest.fixture(scope="module")
def first_build(blender_cmd, tmp_path_factory):
    out = tmp_path_factory.mktemp("e2e out")
    outcome = run_build(parse_project(copy.deepcopy(DEMO)), options(out))
    assert outcome.status == "completed", outcome.message
    return out, outcome


def test_full_demo_build_smoke(blender_cmd, first_build, tmp_path):
    _, outcome = first_build
    rev = outcome.revision_dir
    for cam_id in CANONICAL_CAMERA_IDS:
        assert validate_png(rev / "images" / f"{cam_id}.png", 128, 72) is None, cam_id
    assert verify_delivery(rev) == []
    delivery = json.loads((rev / "delivery.json").read_text(encoding="utf-8"))
    assert delivery["blender_version"].startswith("Blender 5.2.2")
    assert delivery["python_versions"]["blender"].startswith("3.13")
    assert delivery["complete"] is True

    report = inspect(blender_cmd, tmp_path, blend=rev / "model.blend")
    assert len(report["cameras"]) == 10
    plan = json.loads((rev / "scene_plan.json").read_text(encoding="utf-8"))
    assert {o["name"] for o in plan["objects"]} <= set(report["objects"])

    glb = inspect(blender_cmd, tmp_path, glb=rev / "model.glb")["objects"]
    assert glb["Wall_Front"]["bbox_min"] == pytest.approx([-2.25, 5.0, 0.0], abs=TOL)
    assert glb["Wall_Front"]["bbox_max"] == pytest.approx([2.25, 5.2, 3.6], abs=TOL)


def test_changed_parameters_real_geometry(blender_cmd, first_build, tmp_path):
    out, first = first_build
    data = copy.deepcopy(DEMO)
    data["building"]["footprint_width"]["value"] = 4.0
    data["building"]["wall_height"]["value"] = 3.2
    w01 = next(o for o in data["building"]["openings"] if o["id"] == "W01")
    w01["offset"]["value"] = 2.0
    outcome = run_build(parse_project(data), options(out))
    assert outcome.status == "completed", outcome.message
    assert outcome.revision_dir != first.revision_dir

    rays = [
        {
            "object": "Wall_Front",
            "origin": [0.8, 4.9, 1.6],
            "direction": [0, 1, 0],
            "distance": 0.4,
        },
        {
            "object": "Wall_Front",
            "origin": [-1.9, 4.9, 1.6],
            "direction": [0, 1, 0],
            "distance": 0.4,
        },
    ]
    report = inspect(blender_cmd, tmp_path, blend=outcome.revision_dir / "model.blend", rays=rays)
    wall = report["objects"]["Wall_Front"]
    assert wall["bbox_min"] == pytest.approx([-2.0, 5.0, 0.0], abs=TOL)
    assert wall["bbox_max"] == pytest.approx([2.0, 5.2, 3.2], abs=TOL)
    assert report["rays"] == [False, True]

    assert verify_delivery(first.revision_dir) == []
    old = sha256_file(first.revision_dir / "images" / "01_front.png")
    assert sha256_file(outcome.revision_dir / "images" / "01_front.png") != old


def test_relative_out_dir_real_blender(blender_cmd, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outcome = run_build(parse_project(copy.deepcopy(DEMO)), options(Path("rel out")))
    assert outcome.status == "completed", outcome.message
    assert outcome.revision_dir.is_relative_to(tmp_path)
    assert verify_delivery(outcome.revision_dir) == []


def test_cancel_then_resume_real_blender(blender_cmd, tmp_path):
    project = parse_project(copy.deepcopy(DEMO))
    out = tmp_path / "cancel out"
    cancel = threading.Event()
    outcome = run_build(
        project, options(out, SLOW, cancel=cancel, on_progress=lambda *_: cancel.set())
    )
    assert outcome.status == "cancelled", outcome.message
    kept = outcome.rendered_now
    assert 1 <= len(kept) < 10
    for cam_id in kept:
        assert (outcome.revision_dir / "images" / f"{cam_id}.png").is_file()

    resumed = run_build(project, options(out, SLOW))
    assert resumed.status == "completed", resumed.message
    assert set(resumed.rendered_now).isdisjoint(kept)
    assert sorted(resumed.rendered_now + kept) == sorted(CANONICAL_CAMERA_IDS)
    assert verify_delivery(resumed.revision_dir) == []

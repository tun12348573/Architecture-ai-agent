import json

import pytest

from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import TOL, load_project
from exterior_agent.geometry.scene_plan import (
    build_scene_plan,
    required_material_names,
    required_object_names,
)
from exterior_agent.geometry.walls import opening_boxes
from tests.integration.conftest import DEMO_PATH, inspect, run_script

pytestmark = pytest.mark.blender


@pytest.fixture(scope="module")
def built(blender_cmd, tmp_path_factory):
    work = tmp_path_factory.mktemp("scene with space")
    project = load_project(DEMO_PATH)
    plan = build_scene_plan(project, resolve_render("smoke"))
    plan_path = work / "scene_plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    blend, glb = work / "model.blend", work / "model.glb"
    lines = run_script(
        blender_cmd,
        "build_scene.py",
        ["--plan", str(plan_path), "--blend", str(blend), "--glb", str(glb)],
        work / "build.log",
    )
    assert any(line.startswith("EA_RESULT ") for line in lines)
    return {"work": work, "plan": plan, "project": project, "blend": blend, "glb": glb}


@pytest.fixture(scope="module")
def blend_report(blender_cmd, built):
    project = built["project"]
    rays = []
    for opening_id in ("D01", "W01"):
        lo, hi = opening_boxes(project)[opening_id]
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        rays.append(
            {
                "object": "Wall_Front",
                "origin": [cx, 4.9, cz],
                "direction": [0, 1, 0],
                "distance": 0.4,
            }
        )
    rays.append(
        {
            "object": "Wall_Front",
            "origin": [-1.85, 4.9, 1.2],
            "direction": [0, 1, 0],
            "distance": 0.4,
        }
    )
    return inspect(blender_cmd, built["work"], blend=built["blend"], rays=rays)


def assert_bbox(entry, lo, hi):
    assert entry["bbox_min"] == pytest.approx(lo, abs=TOL)
    assert entry["bbox_max"] == pytest.approx(hi, abs=TOL)


def test_no_temp_files_left(built):
    leftovers = [p.name for p in built["work"].iterdir() if ".tmp" in p.name]
    assert leftovers == []


def test_blend_contains_named_editable_objects(built, blend_report):
    objects = blend_report["objects"]
    plan = built["plan"]
    assert required_object_names(plan) <= set(objects)
    expected = {o["name"]: o["collection"] for o in plan["objects"]}
    for name, collection in expected.items():
        assert collection in objects[name]["collections"], name
    assert required_material_names(plan) <= set(blend_report["materials"])
    assert objects["Wall_Front"]["materials"] == ["MAT_Wall"]
    assert len(blend_report["cameras"]) == 10
    assert blend_report["cameras"]["CAM_09_top"]["projection"] == "ORTHO"
    assert blend_report["cameras"]["CAM_01_front"]["projection"] == "PERSP"


def test_blend_dimensions_within_tolerance(blend_report):
    objects = blend_report["objects"]
    assert_bbox(objects["Wall_Front"], [-2.25, 5.0, 0.0], [2.25, 5.2, 3.6])
    assert_bbox(objects["Wall_Left"], [-2.25, 5.2, 0.0], [-2.05, 16.8, 3.6])
    assert_bbox(objects["Roof_Slab"], [-2.25, 5.0, 3.6], [2.25, 17.0, 3.75])


def test_openings_are_real_holes_in_blender(blend_report):
    assert blend_report["rays"] == [False, False, True]


def test_glb_reimport_matches(blender_cmd, built):
    report = inspect(blender_cmd, built["work"], glb=built["glb"])
    objects = report["objects"]
    assert_bbox(objects["Wall_Front"], [-2.25, 5.0, 0.0], [2.25, 5.2, 3.6])
    assert_bbox(objects["Wall_Right"], [2.05, 5.2, 0.0], [2.25, 16.8, 3.6])
    assert_bbox(objects["Roof_Slab"], [-2.25, 5.0, 3.6], [2.25, 17.0, 3.75])
    assert required_material_names(built["plan"]) <= set(report["materials"])


def test_render_two_views_smoke(blender_cmd, built):
    from PIL import Image

    images = built["work"] / "images"
    lines = run_script(
        blender_cmd,
        "render_views.py",
        ["--blend", str(built["blend"]), "--images", str(images), "--cameras", "01_front,09_top"],
        built["work"] / "render.log",
    )
    assert sorted(p.name for p in images.iterdir()) == ["01_front.png", "09_top.png"]
    for name in ("01_front.png", "09_top.png"):
        with Image.open(images / name) as img:
            assert img.size == (128, 72)
    assert len([line for line in lines if line.startswith("EA_PROGRESS ")]) == 2

import json

import pytest

from exterior_agent.domain.project import CANONICAL_CAMERA_IDS
from exterior_agent.domain.render import RenderSettings, resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.geometry.scene_plan import (
    build_scene_plan,
    required_material_names,
    required_object_names,
)

DEMO_OBJECTS = {
    "Wall_Front",
    "Wall_Rear",
    "Wall_Left",
    "Wall_Right",
    "Roof_Slab",
    "Opening_D01",
    "Opening_W01",
    "Opening_D02",
    "Opening_W02",
    "Door_D01",
    "Door_D02",
    "Window_W01",
    "Window_W02",
    "Site_Land",
    "Site_Context",
}
MATERIALS = {
    "MAT_Wall",
    "MAT_Roof",
    "MAT_Door",
    "MAT_Window_Glass",
    "MAT_Land",
    "MAT_Context_Ground",
}


def test_smoke_profile():
    assert resolve_render("smoke") == RenderSettings("smoke", 128, 72, "CYCLES", "CPU", 4)


def test_preview_and_final_profiles():
    assert resolve_render("preview") == RenderSettings(
        "preview", 1280, 720, "BLENDER_EEVEE", None, 16
    )
    assert resolve_render("final") == RenderSettings("final", 1920, 1080, "CYCLES", "GPU", 128)


def test_cycles_gpu_override():
    settings = resolve_render("preview", engine="cycles", device="gpu")
    assert (settings.engine, settings.device, settings.width) == ("CYCLES", "GPU", 1280)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"profile": "preview", "device": "gpu"},
        {"profile": "huge"},
        {"profile": "smoke", "engine": "x"},
    ],
)
def test_invalid_render_requests(kwargs):
    with pytest.raises(ValueError):
        resolve_render(**kwargs)


@pytest.fixture
def plan(demo_data):
    return build_scene_plan(parse_project(demo_data), resolve_render("smoke"))


def test_plan_objects_and_materials(plan):
    assert required_object_names(plan) == DEMO_OBJECTS
    assert required_material_names(plan) == MATERIALS
    for obj in plan["objects"]:
        if obj["type"] == "MESH":
            assert obj["material"] in MATERIALS, obj["name"]
            assert obj["faces"] and obj["vertices"], obj["name"]
    collections = {o["name"]: o["collection"] for o in plan["objects"]}
    assert collections["Wall_Front"] == "Building"
    assert collections["Opening_W01"] == "Openings"
    assert collections["Door_D01"] == "Doors"
    assert collections["Window_W02"] == "Windows"
    assert collections["Site_Land"] == "Site"


def test_plan_cameras(plan):
    assert [c["id"] for c in plan["cameras"]] == list(CANONICAL_CAMERA_IDS)
    assert [c["name"] for c in plan["cameras"]] == [f"CAM_{i}" for i in CANONICAL_CAMERA_IDS]
    top = plan["cameras"][8]
    assert top["projection"] == "ORTHO" and top["ortho_scale"] > 0


def test_plan_is_deterministic_json(demo_data, plan):
    again = build_scene_plan(parse_project(demo_data), resolve_render("smoke"))
    assert json.dumps(plan, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert plan["render"] == resolve_render("smoke").to_dict()


def test_plan_follows_parameters(demo_data):
    demo_data["building"]["wall_height"]["value"] = 3.2
    plan = build_scene_plan(parse_project(demo_data), resolve_render("smoke"))
    wall = next(o for o in plan["objects"] if o["name"] == "Wall_Front")
    assert max(v[2] for v in wall["vertices"]) == pytest.approx(3.2)


def test_transmission_only_when_set(modern_data, demo_data):
    smoke = resolve_render("smoke")
    modern = build_scene_plan(parse_project(modern_data), smoke)
    glass = next(m for m in modern["materials"] if m["name"] == "MAT_Glass")
    assert glass["transmission"] == 1.0
    demo = build_scene_plan(parse_project(demo_data), smoke)
    assert all("transmission" not in m for m in demo["materials"])

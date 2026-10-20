"""The neoclassical template in the scene plan: materials, cameras, site, street context."""

import pytest

from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.geometry.scene_plan import build_scene_plan, template_bounds

SMOKE, PREVIEW = resolve_render("smoke"), resolve_render("preview")


def test_classic_plan_builds_smoke_and_preview(classic_data):
    p = parse_project(classic_data)
    smoke = build_scene_plan(p, SMOKE)
    assert "Bay_Columns" in {o["name"] for o in smoke["objects"]}
    preview = build_scene_plan(p, PREVIEW)
    tiles = next(m for m in preview["materials"] if m["name"] == "MAT_Roof_Tiles")
    assert tiles["textures"]["base_color"]["path"].startswith("materials/clay_roof_tiles/")


def test_every_material_used_and_known(classic_data):
    plan = build_scene_plan(parse_project(classic_data), SMOKE)
    used = {o["material"] for o in plan["objects"] if o["type"] == "MESH"}
    assert {m["name"] for m in plan["materials"]} == used


def test_cameras_fit_roof(classic_data):
    p = parse_project(classic_data)
    building, _ = template_bounds(p)
    plan = build_scene_plan(p, SMOKE)
    ridge = max(v[2] for o in plan["objects"] if o["name"] == "Roof_Tiles_L" for v in o["vertices"])
    assert building[1][2] >= ridge - 1e-9


def test_metallic_only_when_set(classic_data, demo_data):
    plan = build_scene_plan(parse_project(classic_data), SMOKE)
    iron = next(m for m in plan["materials"] if m["name"] == "MAT_Iron")
    assert iron["metallic"] == 0.7
    demo = build_scene_plan(parse_project(demo_data), SMOKE)
    assert all("metallic" not in m for m in demo["materials"])


def test_classic_pots_ignored(classic_data):
    classic_data["context"]["pots"]["value"] = True
    plan = build_scene_plan(parse_project(classic_data), PREVIEW)
    assert not [a for a in plan.get("assets", []) if a["name"].startswith("Pot_")]


def test_gate_piers(classic_data):
    plan = build_scene_plan(parse_project(classic_data), SMOKE)
    objects = {o["name"]: o for o in plan["objects"]}
    for side in ("L", "R"):
        assert objects[f"Gate_Pier_{side}"]["material"] == "MAT_Trim"
        assert objects[f"Gate_Lantern_{side}"]["material"] == "MAT_Iron"
    pier = objects["Gate_Pier_L"]["vertices"]
    fence = objects["Fence_Left"]["vertices"]
    assert max(v[0] for v in fence) <= min(v[0] for v in pier) + 1e-9  # fence stops at the pier
    assert objects["Gate"]["material"] == "MAT_Iron"


def test_classic_street_context(classic_data):
    plan = build_scene_plan(parse_project(classic_data), PREVIEW)
    names = {o["name"] for o in plan["objects"]}
    assert {"Road", "Sidewalk_Front", "Neighbour_L1"} <= names
    trees = [a for a in plan["assets"] if a["name"].startswith("Tree_")]
    assert trees


def test_roof_tile_uvs_follow_slope(classic_data):
    """u runs along the ridge (y), v up the slope in metres, at any allowed pitch."""
    import math

    for pitch in (30.0, 55.0):
        classic_data["classic"]["roof"]["pitch_deg"]["value"] = pitch
        p = parse_project(classic_data)
        plan = build_scene_plan(p, SMOKE)
        w2 = p.classic.footprint_width.value / 2
        for name, eave in (("Roof_Tiles_L", -w2), ("Roof_Tiles_R", w2)):
            o = next(o for o in plan["objects"] if o["name"] == name)
            for face, uvs in zip(o["faces"], o["uvs"], strict=True):
                for i, (u, v) in zip(face, uvs, strict=True):
                    x, y, _ = o["vertices"][i]
                    assert u == pytest.approx(y) and v == pytest.approx(
                        abs(x - eave) / math.cos(math.radians(pitch))
                    )

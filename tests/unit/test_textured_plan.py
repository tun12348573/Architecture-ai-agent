import pytest

from exterior_agent.assets.catalog import load_catalog
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.modern_massing import massing_objects
from exterior_agent.geometry.scene_plan import build_scene_plan, required_asset_files


@pytest.fixture
def project(modern_data):
    return parse_project(modern_data)


def test_smoke_plan_is_flat(project):
    plan = build_scene_plan(project, resolve_render("smoke"))
    assert "world" not in plan and "assets" not in plan
    assert all("textures" not in m for m in plan["materials"])
    assert required_asset_files(plan) == []


def test_preview_plan_references_textures(project):
    plan = build_scene_plan(project, resolve_render("preview"))
    wall = next(m for m in plan["materials"] if m["name"] == "MAT_Wall")
    asset = load_catalog().get("painted_plaster_wall")
    base = next(f for f in asset.files if f.role == "base_color")
    assert wall["textures"]["base_color"] == {
        "path": f"materials/painted_plaster_wall/{base.path}",
        "sha256": base.sha256,
    }
    assert set(wall["textures"]) == {"base_color", "roughness", "normal"}
    assert wall["texture_scale_m"] == asset.scale_m
    glass = next(m for m in plan["materials"] if m["name"] == "MAT_Glass")
    assert "textures" not in glass


def test_world_in_plan(project):
    plan = build_scene_plan(project, resolve_render("final"))
    hdri = load_catalog().get("kloofendal_48d_partly_cloudy_puresky").files[0]
    assert plan["world"] == {
        "hdri": {"path": f"materials/kloofendal_48d_partly_cloudy_puresky/{hdri.path}",
                 "sha256": hdri.sha256},
        "strength": 1.0,
        "rotation_deg": 0.0,
    }  # fmt: skip


def test_plants_inside_planter(project):
    plan = build_scene_plan(project, resolve_render("preview"))
    planter = next(o for o in massing_objects(project) if o.name == "Planter_Roof_1")
    (lo, hi) = planter.mesh.bounds()
    plants = plan["assets"]
    assert len(plants) >= 2 and [a["name"] for a in plants] == [
        f"Plant_Roof_{k}" for k in range(1, len(plants) + 1)
    ]
    assert {a["model"]["path"].split("/")[1] for a in plants} == {"shrub_01", "shrub_02"}
    for a in plants:
        x, y, z = a["location"]
        assert lo[0] < x < hi[0] and lo[1] < y < hi[1]
        assert z == pytest.approx(hi[2], abs=TOL)
        assert a["collection"] == "Roof" and a["includes"]


def test_required_asset_files_complete(project):
    plan = build_scene_plan(project, resolve_render("preview"))
    files = required_asset_files(plan)
    assert len(files) == len(set(files))
    catalog = load_catalog()
    expected = set()
    for asset_id in ("painted_plaster_wall", "kloofendal_48d_partly_cloudy_puresky", "shrub_01"):
        for f in catalog.get(asset_id).files:
            if asset_id != "painted_plaster_wall" or f.role in (
                "base_color",
                "roughness",
                "normal",
            ):
                expected.add((asset_id, f.path, f.sha256))
    assert expected <= set(files)


def test_hdri_plan_softens_sun(project):
    flat = build_scene_plan(project, resolve_render("smoke"))
    textured = build_scene_plan(project, resolve_render("preview"))
    assert textured["sun"]["strength"] < flat["sun"]["strength"]

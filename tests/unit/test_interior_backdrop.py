"""Dark matte panels inside the house so clear glass does not show the sky through it."""

import pytest

from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.modern_interior import backdrop_objects
from exterior_agent.geometry.modern_massing import floor_base_z, floor_front_y
from exterior_agent.geometry.scene_plan import build_scene_plan

SMOKE = resolve_render("smoke")
GLAZED = ("window", "door_4leaf")


@pytest.fixture
def project(modern_data):
    return parse_project(modern_data)


def test_one_backdrop_per_glazed_opening(project):
    m = project.modern
    glazed = {
        o.id
        for f in m.floors
        for side in ("openings_front", "openings_rear")
        for o in getattr(f, side)
        if o.kind in GLAZED
    }
    objects = {o.name: o for o in backdrop_objects(project)}
    assert set(objects) == {f"Backdrop_{i}" for i in glazed}
    assert all(o.collection == "Interior_Backdrop" for o in objects.values())
    assert all(o.material == "MAT_Interior" for o in objects.values())


def test_backdrop_inside_and_covering(project):
    m = project.modern
    t, half = m.wall_thickness.value, m.footprint_width.value / 2
    yr = project.site.front_setback.value + m.footprint_depth.value
    objects = {o.name: o for o in backdrop_objects(project)}
    for n, f in enumerate(m.floors, start=1):
        z0 = floor_base_z(m, n)
        y_in0, y_in1 = floor_front_y(project, n) + t, yr - t
        for side in ("openings_front", "openings_rear"):
            for o in getattr(f, side):
                if o.kind not in GLAZED:
                    continue
                (lo, hi) = objects[f"Backdrop_{o.id}"].mesh.bounds()
                assert lo[1] == pytest.approx(hi[1])  # vertical panel
                assert y_in0 < lo[1] < y_in1, o.id
                assert -half + t - TOL <= lo[0] and hi[0] <= half - t + TOL
                assert lo[2] <= z0 + o.sill.value + TOL
                assert hi[2] >= z0 + o.sill.value + o.height.value - TOL
                if side == "openings_front":
                    x0 = -half + o.offset.value
                    assert lo[0] <= x0 + TOL and hi[0] >= x0 + o.width.value - TOL


def test_no_backdrop_without_clear_glass(modern_data):
    modern_data["materials"]["window_glass"]["value"]["transmission"] = 0.0
    p = parse_project(modern_data)
    assert backdrop_objects(p) == []
    plan = build_scene_plan(p, SMOKE)
    assert "MAT_Interior" not in {m["name"] for m in plan["materials"]}


def test_interior_material_in_plan(project):
    plan = build_scene_plan(project, SMOKE)
    mat = next(m for m in plan["materials"] if m["name"] == "MAT_Interior")
    assert max(mat["base_color"]) < 0.1 and mat["roughness"] >= 0.8

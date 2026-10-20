"""Ground-floor front brick cladding: a thin skin on the facade with the wall's openings."""

import pytest

from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.modern_checks import check_modern_geometry
from exterior_agent.geometry.modern_cladding import cladding_objects
from exterior_agent.geometry.scene_plan import build_scene_plan


@pytest.fixture
def project(modern_data):
    return parse_project(modern_data)


def test_cladding_bounds(project):
    (obj,) = cladding_objects(project)
    assert (obj.name, obj.collection, obj.material) == (
        "Cladding_F1_Front",
        "Facade",
        "MAT_Cladding",
    )
    lo, hi = obj.mesh.bounds()
    # fixture: W 5 m, floor-1 face at y = 4.5, canopy at 2.9 m, cladding 20 mm
    assert lo == pytest.approx((-2.5, 4.48, 0.0), abs=TOL)
    assert hi == pytest.approx((2.5, 4.5, 2.9), abs=TOL)


def test_cladding_has_opening_holes(project):
    (obj,) = cladding_objects(project)
    w = project.modern.footprint_width.value
    for o in project.modern.floors[0].openings_front:
        x0 = -w / 2 + o.offset.value
        x1, z0, z1 = x0 + o.width.value, o.sill.value, o.sill.value + o.height.value
        for face in obj.mesh.faces:
            pts = [obj.mesh.vertices[i] for i in face]
            cx = sum(p[0] for p in pts) / len(pts)
            cz = sum(p[2] for p in pts) / len(pts)
            inside = x0 + TOL < cx < x1 - TOL and z0 + TOL < cz < z1 - TOL
            assert not inside, f"cladding face covers opening {o.id}"


def test_no_cladding_when_absent(modern_data):
    del modern_data["modern"]["cladding"]
    p = parse_project(modern_data)
    assert cladding_objects(p) == []
    plan = build_scene_plan(p, resolve_render("smoke"))
    assert "MAT_Cladding" not in {m["name"] for m in plan["materials"]}


def test_cladding_passes_geometry_checks(project):
    assert check_modern_geometry(project) == []


def test_cladding_in_scene_plan(project):
    plan = build_scene_plan(project, resolve_render("smoke"))
    assert "Cladding_F1_Front" in {o["name"] for o in plan["objects"]}
    assert "MAT_Cladding" in {m["name"] for m in plan["materials"]}

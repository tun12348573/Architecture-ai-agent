"""Neoclassical massing: arched holes, slabs, bay/loggia, clay-tile gable roof, gables, gutters."""

import math

import pytest

from exterior_agent.domain.validate import parse_project
from exterior_agent.geometry.classic_massing import classic_massing_objects
from exterior_agent.geometry.modern_checks import check_classic_geometry
from exterior_agent.geometry.polygon_wall import arch_outline, circle_outline


def objs(data):
    return {o.name: o for o in classic_massing_objects(parse_project(data))}


def inside(pt, poly) -> bool:
    x, y, hit = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def face_centroids(mesh, y):
    """(x, z) centroids of faces lying in the plane y."""
    for f in mesh.faces:
        pts = [mesh.vertices[i] for i in f]
        if all(abs(p[1] - y) < 1e-9 for p in pts):
            yield (sum(p[0] for p in pts) / len(pts), sum(p[2] for p in pts) / len(pts))


def test_expected_names(classic_data):
    names = set(objs(classic_data))
    walls = {f"Floor{n}_Wall_{s}" for n in (1, 2, 3) for s in ("Front", "Rear", "Left", "Right")}
    assert walls | {"Floor1_Slab", "Floor2_Slab", "Floor3_Slab"} <= names
    assert {"Roof_Tiles_L", "Roof_Tiles_R", "Gable_Front", "Gable_Rear", "Gutter_L", "Gutter_R",
            "Bay_Slab_F2", "Bay_Roof"} <= names  # fmt: skip
    assert {f"Opening_{i}" for i in ("D1", "D2", "D3", "W1", "W2", "W5", "W6", "W8")} <= names
    assert {f"Backdrop_{i}" for i in ("D1", "D3", "W2", "W5", "W6")} <= names


def test_arched_holes_real(classic_data):
    o = objs(classic_data)
    p = parse_project(classic_data)
    m, yf = p.classic, p.site.front_setback.value
    d3 = m.floors[1].openings_front[0]
    x0 = -m.footprint_width.value / 2 + d3.offset.value
    z0 = m.floors[0].height.value + d3.sill.value
    hole = arch_outline(x0, x0 + d3.width.value, z0, z0 + d3.height.value)
    centroids = list(face_centroids(o["Floor2_Wall_Front"].mesh, yf))
    assert centroids and not any(inside(c, hole) for c in centroids)
    assert o["Floor2_Wall_Front"].mesh.is_closed()


def test_roof_pitch_and_cover(classic_data):
    o, p = objs(classic_data), parse_project(classic_data)
    m, s = p.classic, p.site
    w2, top = m.footprint_width.value / 2, sum(f.height.value for f in m.floors)
    lo, hi = o["Roof_Tiles_L"].mesh.bounds()
    yf, yr = s.front_setback.value, s.front_setback.value + m.footprint_depth.value
    ov = m.roof.overhang.value
    assert (lo[1], hi[1]) == pytest.approx((yf - ov, yr + ov))
    assert lo[0] == pytest.approx(-w2) and hi[0] == pytest.approx(0.0)
    rise = min(v[2] for v in o["Roof_Tiles_L"].mesh.vertices if abs(v[0]) < 1e-9) - top
    assert rise / w2 == pytest.approx(math.tan(math.radians(40)), abs=1e-6)
    for name in ("Roof_Tiles_L", "Roof_Tiles_R", "Gutter_L", "Gutter_R"):
        lo, hi = o[name].mesh.bounds()
        assert -w2 - 1e-9 <= lo[0] and hi[0] <= w2 + 1e-9, name


def test_gable_oculus_hole(classic_data):
    o, p = objs(classic_data), parse_project(classic_data)
    m = p.classic
    w2, top = m.footprint_width.value / 2, sum(f.height.value for f in m.floors)
    h = w2 * math.tan(math.radians(m.roof.pitch_deg.value))
    oc = circle_outline(0.0, top + 0.4 * h, m.roof.gable_front.oculus_radius.value)
    cents = list(face_centroids(o["Gable_Front"].mesh, p.site.front_setback.value))
    assert cents and not any(inside(c, oc) for c in cents)
    assert o["Gable_Front"].mesh.is_closed()


def test_bay_inside_lot(classic_data):
    o, p = objs(classic_data), parse_project(classic_data)
    lo, hi = o["Bay_Slab_F2"].mesh.bounds()
    w2 = p.classic.footprint_width.value / 2
    assert lo[0] == pytest.approx(-w2) and hi[0] == pytest.approx(-w2 + 2.6)
    assert lo[1] == pytest.approx(p.site.front_setback.value - 0.9) and lo[1] >= 0


def test_bay_right_mirrors(classic_data):
    classic_data["classic"]["bay"]["side"]["value"] = "right"
    classic_data["classic"]["bay"]["pediment"] = None
    o, p = objs(classic_data), parse_project(classic_data)
    w2 = p.classic.footprint_width.value / 2
    lo, hi = o["Bay_Slab_F2"].mesh.bounds()
    assert lo[0] == pytest.approx(w2 - 2.6) and hi[0] == pytest.approx(w2)
    lo, hi = o["Opening_W2"].empty_box  # loggia window stays on the main facade
    assert lo[1] == pytest.approx(p.site.front_setback.value)


def test_enclosed_bay_floor(classic_data):
    classic_data["classic"]["bay"]["to_floor"]["value"] = 3
    classic_data["classic"]["bay"]["pediment"] = None
    o, p = objs(classic_data), parse_project(classic_data)
    yb = p.site.front_setback.value - 0.9
    lo, _ = o["Bay_Wall_F3"].mesh.bounds()
    assert lo[1] == pytest.approx(yb)
    lo, _ = o["Opening_W5"].empty_box  # floor-3 window inside the bay range moves to the bay front
    assert lo[1] == pytest.approx(yb)


def test_steep_roof_limits(classic_data):
    for key in ("width",):
        classic_data["site"][key]["value"] = 8.0
    classic_data["classic"]["footprint_width"]["value"] = 8.0
    classic_data["classic"]["roof"]["pitch_deg"]["value"] = 55.0
    p = parse_project(classic_data)
    o = {x.name: x for x in classic_massing_objects(p)}
    _, hi = o["Roof_Tiles_L"].mesh.bounds()
    assert hi[2] <= 25.0
    test_gable_oculus_hole(classic_data)


def test_classic_geometry_checks_clean(classic_data):
    assert check_classic_geometry(parse_project(classic_data)) == []


def test_all_closed(classic_data):
    for name, o in objs(classic_data).items():
        if o.mesh is not None and not name.startswith("Backdrop_"):
            assert o.mesh.is_closed(), name

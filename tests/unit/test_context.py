"""Street context geometry: road/park, sidewalk, kerb and deterministic neighbour townhouses."""

import pytest

from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.geometry.context import (
    NEIGHBOUR_GAP,
    context_objects,
    neighbour_specs,
)
from exterior_agent.geometry.scene_plan import build_scene_plan

SMOKE = resolve_render("smoke")


def narrow(data: dict) -> dict:
    """3.5 m lot with a 3.5 m house: neighbours sit right next to the side walls."""
    data["site"]["width"]["value"] = 3.5
    data["modern"]["footprint_width"]["value"] = 3.5
    data["modern"]["front_yard"]["gate_width"]["value"] = 2.5
    data["modern"]["louvers"] = []
    for f in data["modern"]["floors"]:
        for side in ("openings_front", "openings_rear"):
            f[side] = f[side][:1]
            for o in f[side]:
                o["offset"]["value"] = 0.3
                o["width"]["value"] = min(o["width"]["value"], 2.6)
    for b in data["modern"]["balconies"]:
        b["offset"]["value"], b["width"]["value"] = 0.35, 2.8  # clear of the frame posts
    return data


@pytest.fixture
def project(modern_data):
    return parse_project(modern_data)


@pytest.mark.parametrize("variant", ["fixture", "narrow"])
def test_context_outside_lot(modern_data, variant):
    p = parse_project(narrow(modern_data) if variant == "narrow" else modern_data)
    half = p.site.width.value / 2
    objects = context_objects(p)
    assert objects and all(o.collection == "Context" for o in objects)
    for o in objects:
        lo, hi = o.mesh.bounds()
        in_front = hi[1] <= 1e-9
        behind = lo[1] >= p.site.depth.value - 1e-9
        gap = 0.0 if o.name.startswith("Ground_") else NEIGHBOUR_GAP  # flat quads may touch
        beside = lo[0] >= half + gap - 1e-9 or hi[0] <= -half - gap + 1e-9
        assert in_front or beside or behind, o.name


def test_neighbours_deterministic(modern_data):
    p = parse_project(modern_data)
    assert neighbour_specs(p) == neighbour_specs(p)
    modern_data["context"]["neighbours"]["seed"]["value"] = 8
    other = neighbour_specs(parse_project(modern_data))
    assert [n.floors for n in other] != [n.floors for n in neighbour_specs(p)]


def test_neighbour_ranges(project):
    specs = neighbour_specs(project)
    assert [n.name for n in specs] == [
        "Neighbour_L1",
        "Neighbour_L2",
        "Neighbour_R1",
        "Neighbour_R2",
    ]
    for n in specs:
        assert 4.0 <= n.x1 - n.x0 <= 6.0 and 2 <= n.floors <= 5, n
        assert project.site.front_setback.value <= n.y0 <= project.site.front_setback.value + 0.8, (
            n
        )  # flush with or behind the house front
    by = {n.name: n for n in specs}
    assert by["Neighbour_L2"].x1 == pytest.approx(by["Neighbour_L1"].x0, abs=1e-9)
    assert by["Neighbour_R2"].x0 == pytest.approx(by["Neighbour_R1"].x1, abs=1e-9)


def test_road_vs_park_parts(modern_data):
    road = {o.name for o in context_objects(parse_project(modern_data))}
    assert {"Road", "Road_Marking", "Sidewalk_Opposite", "Sidewalk_Front", "Kerb_Front"} <= road
    assert "Park_Lawn" not in road
    modern_data["context"]["front"]["value"] = "park"
    park = {o.name for o in context_objects(parse_project(modern_data))}
    assert {"Road", "Park_Lawn", "Sidewalk_Front"} <= park
    assert "Road_Marking" not in park


def test_cameras_ignore_context(modern_data):
    with_context = build_scene_plan(parse_project(modern_data), SMOKE)["cameras"]
    modern_data["context"] = None
    without = build_scene_plan(parse_project(modern_data), SMOKE)["cameras"]
    assert with_context == without


def test_unused_context_materials_not_emitted(modern_data):
    modern_data["context"]["neighbours"]["per_side"]["value"] = 0
    plan = build_scene_plan(parse_project(modern_data), SMOKE)
    names = {m["name"] for m in plan["materials"]}
    assert not any(n.startswith("MAT_Neighbour_") and n != "MAT_Neighbour_Glass" for n in names)
    used = {o["material"] for o in plan["objects"] if o["type"] == "MESH"}
    assert names <= used


def test_neighbour_materials_are_tinted(project):
    plan = build_scene_plan(project, SMOKE)
    tints = [m for m in plan["materials"] if m["name"].startswith("MAT_Neighbour_")]
    walls = [m for m in tints if m["name"] != "MAT_Neighbour_Glass"]
    # neighbour_wall is white in the fixture: every tint must visibly change it
    assert walls and all(m["base_color"] != [1.0, 1.0, 1.0] for m in walls)
    used = {o["material"] for o in plan["objects"] if o["name"].startswith("Neighbour_")}
    assert {m["name"] for m in tints} == used


def test_site_context_below_road(project):
    plan = build_scene_plan(project, SMOKE)
    ground = next(o for o in plan["objects"] if o["name"] == "Site_Context")
    road = next(o for o in plan["objects"] if o["name"] == "Road")
    assert max(v[2] for v in ground["vertices"]) < min(v[2] for v in road["vertices"])


def test_no_car_in_fixture(project):
    plan = build_scene_plan(project, SMOKE)
    assert not [o["name"] for o in plan["objects"] if o["name"].startswith("Prop_")]


def test_neighbours_not_taller_than_house(modern_data):
    # taller neighbours hid the house in 10_aerial (benchmark 2026-10-20)
    for seed in range(20):
        modern_data["context"]["neighbours"]["seed"]["value"] = seed
        p = parse_project(modern_data)
        assert all(2 <= n.floors <= len(p.modern.floors) for n in neighbour_specs(p)), seed


def test_far_ground_covers_view(project):
    from exterior_agent.geometry.scene_plan import CAMERA_CLIP_END

    plan = build_scene_plan(project, SMOKE)
    ground = next(o for o in plan["objects"] if o["name"] == "Site_Context")
    xs = [v[0] for v in ground["vertices"]]
    assert max(xs) - min(xs) >= 2 * CAMERA_CLIP_END


def test_ground_closes_around_lot(project):
    """z = 0 ground beside, behind and under the lot: no ledge down to the far ground."""
    half, depth = project.site.width.value / 2, project.site.depth.value
    quads = [o for o in context_objects(project) if o.name.startswith("Ground_")]
    from exterior_agent.geometry.modern_site import site_objects

    quads += [o for o in site_objects(project) if o.name == "Lot_Base"]

    def covered(x, y):
        for o in quads:
            lo, hi = o.mesh.bounds()
            if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and abs(hi[2]) <= 0.01:
                return True
        return False

    for x, y in ((half + 0.001, 5), (-half - 0.001, 5), (0, depth + 1), (half + 1, depth + 30),
                 (0, depth / 2)):  # fmt: skip
        assert covered(x, y), (x, y)


def _segment_hits_box(a, b, lo, hi) -> bool:
    t0, t1 = 0.0, 1.0
    for k in range(3):
        d = b[k] - a[k]
        if abs(d) < 1e-12:
            if not lo[k] <= a[k] <= hi[k]:
                return False
            continue
        u0, u1 = (lo[k] - a[k]) / d, (hi[k] - a[k]) / d
        t0, t1 = max(t0, min(u0, u1)), min(t1, max(u0, u1))
        if t0 > t1:
            return False
    return True


def test_neighbours_leave_oblique_views_open(project):
    """05/06 see the whole main facade: no neighbour stands in front of the house's front line.

    Set-back upper floors are excluded: seen from a low oblique, a neighbour's side wall always
    hides part of a floor that steps back behind the street line.
    """
    from exterior_agent.geometry.modern_massing import floor_base_z, floor_front_y

    m = project.modern
    plan = build_scene_plan(project, SMOKE)
    cams = [
        c["location"] for c in plan["cameras"] if c["id"] in ("05_front_left", "06_front_right")
    ]
    w = m.footprint_width.value
    targets = [
        (x, floor_front_y(project, n) - 0.05, floor_base_z(m, n) + m.floors[n - 1].height.value / 2)
        for n in range(1, len(m.floors) + 1)
        if floor_front_y(project, n) == floor_front_y(project, 1)
        for x in (-w / 4, 0.0, w / 4)
    ]
    for n in neighbour_specs(project):
        lo, hi = (n.x0, n.y0, 0.0), (n.x1, n.y1, n.floors * 3.3)
        for c in cams:
            for t in targets:
                assert not _segment_hits_box(c, t, lo, hi), (n.name, c, t)

import itertools

import pytest

from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.walls import (
    build_walls,
    door_window_meshes,
    opening_boxes,
    roof_mesh,
    wall_mesh,
)
from tests.unit.geom_helpers import box_overlap_volume, point_inside


@pytest.fixture
def demo(demo_data):
    return parse_project(demo_data)


def assert_bounds(bounds, expected):
    for got_corner, want_corner in zip(bounds, expected, strict=True):
        assert got_corner == pytest.approx(want_corner, abs=TOL)


@pytest.mark.parametrize(
    "holes",
    [[], [(1.0, 2.0, 0.0, 2.4)], [(0.6, 1.6, 0.0, 2.4), (2.3, 3.9, 0.9, 2.3)]],
    ids=["solid", "door", "door+window"],
)
def test_wall_mesh_is_closed_with_and_without_holes(holes):
    assert wall_mesh(4.5, 3.6, 0.2, holes).is_closed()


def test_wall_has_real_hole(demo):
    walls = build_walls(demo)
    boxes = opening_boxes(demo)
    for o in demo.building.openings:
        wall = walls[f"Wall_{o.wall.capitalize()}"]
        lo, hi = boxes[o.id]
        centre = tuple((a + b) / 2 for a, b in zip(lo, hi, strict=True))
        assert not point_inside(wall, centre), o.id
        beside = (lo[0] - 0.05, centre[1], centre[2])
        assert point_inside(wall, beside), o.id


def test_wall_dimensions_within_tolerance(demo):
    walls = build_walls(demo)
    assert_bounds(walls["Wall_Front"].bounds(), ((-2.25, 5.0, 0.0), (2.25, 5.2, 3.6)))
    assert_bounds(walls["Wall_Rear"].bounds(), ((-2.25, 16.8, 0.0), (2.25, 17.0, 3.6)))
    assert_bounds(walls["Wall_Left"].bounds(), ((-2.25, 5.2, 0.0), (-2.05, 16.8, 3.6)))
    assert_bounds(walls["Wall_Right"].bounds(), ((2.05, 5.2, 0.0), (2.25, 16.8, 3.6)))
    assert_bounds(roof_mesh(demo).bounds(), ((-2.25, 5.0, 3.6), (2.25, 17.0, 3.75)))


def _with_side_opening(demo_data, wall):
    demo_data["building"]["openings"].append(
        {
            "id": "S01",
            "kind": "window",
            "wall": wall,
            **{
                k: {
                    "value": v,
                    "unit": "m",
                    "source": "test",
                    "source_ref": "t",
                    "status": "confirmed",
                }
                for k, v in {"offset": 1.0, "width": 1.0, "height": 1.0, "sill": 1.0}.items()
            },
        }
    )
    return parse_project(demo_data)


def test_opening_left_end_convention(demo, demo_data):
    boxes = opening_boxes(demo)
    assert (boxes["W01"][0][0], boxes["W01"][1][0]) == pytest.approx((0.05, 1.65), abs=TOL)
    assert (boxes["W02"][0][0], boxes["W02"][1][0]) == pytest.approx((-1.45, -0.25), abs=TOL)
    import copy

    right = opening_boxes(_with_side_opening(copy.deepcopy(demo_data), "right"))["S01"]
    assert (right[0][1], right[1][1]) == pytest.approx((6.0, 7.0), abs=TOL)
    assert right[0][0] == pytest.approx(2.05, abs=TOL)
    left = opening_boxes(_with_side_opening(demo_data, "left"))["S01"]
    assert (left[0][1], left[1][1]) == pytest.approx((15.0, 16.0), abs=TOL)
    assert left[1][0] == pytest.approx(-2.05, abs=TOL)


def test_side_wall_opening_is_real_hole(demo_data):
    project = _with_side_opening(demo_data, "right")
    lo, hi = opening_boxes(project)["S01"]
    centre = tuple((a + b) / 2 for a, b in zip(lo, hi, strict=True))
    wall = build_walls(project)["Wall_Right"]
    assert wall.is_closed()
    assert not point_inside(wall, centre)
    assert point_inside(wall, (centre[0], lo[1] - 0.05, centre[2]))


def test_walls_do_not_overlap(demo):
    walls = build_walls(demo)
    for a, b in itertools.combinations(walls.values(), 2):
        assert box_overlap_volume(a.bounds(), b.bounds()) == pytest.approx(0.0, abs=1e-9)


def test_doors_windows_inside_openings(demo):
    boxes = opening_boxes(demo)
    meshes = door_window_meshes(demo)
    assert set(meshes) == {"Door_D01", "Window_W01", "Door_D02", "Window_W02"}
    for name, mesh in meshes.items():
        lo, hi = boxes[name.split("_", 1)[1]]
        mlo, mhi = mesh.bounds()
        for axis in range(3):
            assert mlo[axis] >= lo[axis] - TOL and mhi[axis] <= hi[axis] + TOL, (name, axis)


def _set_opening(data, opening_id, **values):
    o = next(o for o in data["building"]["openings"] if o["id"] == opening_id)
    for key, value in values.items():
        o[key]["value"] = value


def _assert_clean_walls(project):
    for name, mesh in build_walls(project).items():
        assert mesh.is_closed(), name
        for face in mesh.faces:
            assert len(set(face)) == len(face), (name, face)


def test_head_aligned_openings_give_closed_walls(demo_data):
    # 0.7 + 1.4 == 2.0999999999999996 in floating point, D01 head is 2.1
    _set_opening(demo_data, "D01", height=2.1)
    _set_opening(demo_data, "W01", sill=0.7, height=1.4)
    _assert_clean_walls(parse_project(demo_data))


def test_mm_project_gives_closed_walls(demo_data):
    _set_opening(demo_data, "D01", height=2.3)
    _set_opening(demo_data, "W01", sill=0.9, height=1.4)
    for node in [demo_data["building"][k] for k in ("footprint_width", "wall_thickness")] + [
        o[k]
        for o in demo_data["building"]["openings"]
        for k in ("offset", "width", "height", "sill")
    ]:
        node["value"] = round(node["value"] * 1000, 6)
        node["unit"] = "mm"
    _assert_clean_walls(parse_project(demo_data))


@pytest.mark.parametrize("offset", [0.2, 10.8], ids=["near_end", "far_end"])
@pytest.mark.parametrize("wall", ["left", "right"])
def test_side_wall_openings_on_limits_give_closed_walls(demo_data, wall, offset):
    project = _with_side_opening(demo_data, wall)
    data = project.model_dump(mode="json")
    data["building"]["openings"][-1]["offset"]["value"] = offset
    data["building"]["openings"][-1]["offset"]["original"] = None
    _assert_clean_walls(parse_project(data))

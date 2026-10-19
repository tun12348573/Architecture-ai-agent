import pytest

from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.modern_massing import floor_base_z, massing_objects
from tests.unit.geom_helpers import point_inside


@pytest.fixture
def objects(modern_data):
    return {o.name: o for o in massing_objects(parse_project(modern_data))}


def bounds(obj):
    return obj.mesh.bounds() if obj.mesh is not None else obj.empty_box


def test_floor_bases(modern_data):
    m = parse_project(modern_data).modern
    assert [floor_base_z(m, n) for n in (1, 2, 3)] == pytest.approx([0.0, 3.6, 6.9])


def test_floor_walls_closed_and_placed(objects):
    for n in (1, 2, 3):
        for side in ("Front", "Rear", "Left", "Right"):
            wall = objects[f"Floor{n}_Wall_{side}"]
            assert wall.mesh.is_closed(), wall.name
            assert wall.collection == "Building" and wall.material == "MAT_Wall"
    (lo, hi) = bounds(objects["Floor3_Wall_Front"])
    assert (lo[1], lo[2], hi[2]) == pytest.approx((6.5, 6.9, 6.9 + 3.15), abs=TOL)
    assert bounds(objects["Floor1_Wall_Front"])[1][2] == pytest.approx(3.45, abs=TOL)
    assert bounds(objects["Floor1_Wall_Left"])[0][1] == pytest.approx(4.7, abs=TOL)


def test_slabs(objects):
    lo, hi = bounds(objects["Floor3_Slab"])
    assert (lo[1], lo[2], hi[2]) == pytest.approx((6.5, 10.05, 10.2), abs=TOL)
    assert objects["Floor3_Slab"].material == "MAT_Roof"
    lo, hi = bounds(objects["Floor2_Slab"])
    assert (lo[1], hi[1]) == pytest.approx((4.5, 19.0), abs=TOL)
    assert objects["Floor2_Slab"].material == "MAT_Terrace_Floor"


def test_terrace_only_where_floor_steps_back(objects):
    terrace = {n for n in objects if "Terrace" in n}
    assert terrace == {"Floor2_Terrace_Rail", "Floor2_Terrace_Pergola"}
    lo, hi = bounds(objects["Floor2_Terrace_Rail"])
    assert (lo[0], hi[0], lo[1], lo[2], hi[2]) == pytest.approx((-2.5, 2.5, 4.5, 6.9, 8.0), abs=TOL)
    plo, phi = bounds(objects["Floor2_Terrace_Pergola"])
    assert plo[1] >= 4.5 - TOL and phi[1] <= 6.5 + TOL and plo[2] == pytest.approx(6.9, abs=TOL)


def test_parapet_and_stair_head(objects):
    parapet = objects["Parapet"]
    assert parapet.mesh.is_closed()
    lo, hi = bounds(parapet)
    assert (lo[2], hi[2], lo[1], hi[1]) == pytest.approx((10.2, 11.3, 6.5, 19.0), abs=TOL)
    slo, shi = bounds(objects["StairHead"])
    assert shi[1] == pytest.approx(19.0 - 0.15, abs=TOL)  # touches rear parapet inner face
    assert (slo[0], shi[0]) == pytest.approx((-1.5, 1.5), abs=TOL)
    assert (slo[2], shi[2]) == pytest.approx((10.2, 13.0), abs=TOL)


def test_roof_garden(objects):
    planters = [o for n, o in objects.items() if n.startswith("Planter_Roof_")]
    assert planters and all(o.collection == "Roof" for o in planters)
    for p in planters:
        lo, hi = bounds(p)
        assert lo[1] >= 6.5 + 0.15 - TOL and lo[2] == pytest.approx(10.2, abs=TOL)
    rlo, rhi = bounds(objects["Roof_Pergola"])
    slo, _ = bounds(objects["StairHead"])
    assert rhi[1] <= slo[1] + TOL and rlo[2] == pytest.approx(10.2, abs=TOL)


def test_openings_are_real_holes(objects):
    empties = {n: o for n, o in objects.items() if n.startswith("Opening_")}
    assert set(empties) == {f"Opening_{i}" for i in ("D1", "D2", "W1", "W2", "W3", "W4", "W5")}
    wall_of = {"D1": "Floor1_Wall_Front", "D2": "Floor1_Wall_Rear", "W1": "Floor1_Wall_Rear",
               "W2": "Floor2_Wall_Front", "W3": "Floor2_Wall_Rear",
               "W4": "Floor3_Wall_Front", "W5": "Floor3_Wall_Rear"}  # fmt: skip
    for oid, wall in wall_of.items():
        lo, hi = empties[f"Opening_{oid}"].empty_box
        centre = tuple((a + b) / 2 for a, b in zip(lo, hi, strict=True))
        assert not point_inside(objects[wall].mesh, centre), oid
        assert point_inside(objects[wall].mesh, (lo[0] - 0.05, centre[1], centre[2])) or (
            point_inside(objects[wall].mesh, (hi[0] + 0.05, centre[1], centre[2]))
        ), oid


def test_single_floor_modern(modern_data):
    m = modern_data["modern"]
    m["floors"] = m["floors"][:1]
    m["balconies"], m["frames"], m["louvers"] = [], [], []
    objects = {o.name: o for o in massing_objects(parse_project(modern_data))}
    assert not [n for n in objects if "Terrace" in n]
    assert bounds(objects["Parapet"])[0][2] == pytest.approx(3.6, abs=TOL)
    assert bounds(objects["StairHead"])[0][2] == pytest.approx(3.6, abs=TOL)
    assert objects["Floor1_Slab"].material == "MAT_Roof"

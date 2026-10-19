import pytest

from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.modern_site import FENCE_THICKNESS, site_objects
from tests.unit.geom_helpers import box_overlap_volume


def objs(data):
    return {o.name: o for o in site_objects(parse_project(data))}


def b(obj):
    return obj.mesh.bounds()


def flat(bounds):
    return (*bounds[0], *bounds[1])


def test_yards(modern_data):
    o = objs(modern_data)
    assert flat(b(o["Yard_Front"])) == pytest.approx((-2.5, 0.0, 0.0, 2.5, 4.5, 0.0), abs=TOL)
    assert o["Yard_Front"].material == "MAT_Paving"
    assert flat(b(o["Yard_Rear"])) == pytest.approx((-2.5, 19.0, 0.0, 2.5, 20.0, 0.0), abs=TOL)
    assert o["Yard_Rear"].material == "MAT_Grass"
    assert o["Site_Context"].collection == "Site"


def test_fence_and_gate_cover_front_boundary(modern_data):
    o = objs(modern_data)
    left, gate, right = b(o["Fence_Left"]), b(o["Gate"]), b(o["Fence_Right"])
    assert left[0][0] == pytest.approx(-2.5) and right[1][0] == pytest.approx(2.5)
    assert left[1][0] == pytest.approx(gate[0][0]) and gate[1][0] == pytest.approx(right[0][0])
    assert gate[1][0] - gate[0][0] == pytest.approx(3.5, abs=TOL)
    assert (gate[0][0] + gate[1][0]) / 2 == pytest.approx(0.0, abs=TOL)
    assert gate[1][2] == pytest.approx(1.6, abs=TOL) and left[1][2] == pytest.approx(1.6)
    for box in (left, gate, right):
        assert box[0][1] >= -TOL and box[1][1] <= FENCE_THICKNESS + TOL


def test_car_and_motorbikes_fit(modern_data):
    o = objs(modern_data)
    car = b(o["Prop_Car"])
    assert car[0][1] >= FENCE_THICKNESS - TOL and car[1][1] <= 4.5 + TOL
    assert car[1][1] - car[0][1] == pytest.approx(4.4, abs=TOL)
    assert car[1][2] <= 1.5 + TOL  # below the canopy (2.9) and balcony (3.45)
    bikes = [b(o[f"Prop_Motorbike_{k}"]) for k in (1, 2)]
    for bike in bikes:
        assert bike[0][0] >= -2.5 - TOL and bike[1][0] <= 2.5 + TOL
        assert bike[0][1] >= FENCE_THICKNESS - TOL and bike[1][1] <= 4.5 + TOL
        assert box_overlap_volume(bike, car) == pytest.approx(0.0, abs=1e-12)
    assert box_overlap_volume(bikes[0], bikes[1]) == pytest.approx(0.0, abs=1e-12)
    assert all(
        o[n].collection == "Props" and o[n].material == "MAT_Props" for n in o if "Prop_" in n
    )


def test_four_motorbikes_fit(modern_data):
    modern_data["modern"]["front_yard"]["motorbikes"]["value"] = 4
    o = objs(modern_data)
    boxes = [b(o["Prop_Car"])] + [b(o[f"Prop_Motorbike_{k}"]) for k in range(1, 5)]
    for i, a in enumerate(boxes):
        assert a[0][0] >= -2.5 - TOL and a[1][0] <= 2.5 + TOL
        for c in boxes[i + 1 :]:
            assert box_overlap_volume(a, c) == pytest.approx(0.0, abs=1e-12)


def test_garden_without_props(modern_data):
    yard = modern_data["modern"]["front_yard"]
    yard["kind"]["value"] = "garden"
    yard["car"]["value"] = False
    yard["motorbikes"]["value"] = 0
    o = objs(modern_data)
    assert not [n for n in o if n.startswith("Prop_")]
    assert o["Yard_Front"].material == "MAT_Grass"


def test_motorbikes_without_car_do_not_overlap(modern_data):
    modern_data["modern"]["front_yard"]["car"]["value"] = False
    modern_data["modern"]["front_yard"]["motorbikes"]["value"] = 3
    o = objs(modern_data)
    bikes = [b(o[f"Prop_Motorbike_{k}"]) for k in (1, 2, 3)]
    for i, a in enumerate(bikes):
        assert a[0][0] >= -2.5 - TOL and a[1][0] <= 2.5 + TOL
        for c in bikes[i + 1 :]:
            assert box_overlap_volume(a, c) == pytest.approx(0.0, abs=1e-12)

"""Generic geometric validation: any accepted parameter combination must give geometry that
stays inside the lot, has unique object names and no parts passing through each other."""

import copy

import pytest

from exterior_agent.domain.validate import ProjectValidationError, parse_project
from tests.unit.conftest import with_props


@pytest.fixture
def modern_data(modern_data):
    return with_props(modern_data)


def P(v, unit="m"):
    return {"value": v, "unit": unit, "source": "test", "source_ref": "t", "status": "confirmed"}


def C(v):
    return P(v, "count")


def frame(a, b):
    return {"from_floor": C(a), "to_floor": C(b), "thickness": P(0.3), "depth": P(0.4)}


def messages(data) -> str:
    with pytest.raises(ProjectValidationError) as exc:
        parse_project(data)
    return " | ".join(f"{i.path}: {i.message}" for i in exc.value.issues)


def m(data):
    return data["modern"]


def _frame_floor1(d):
    m(d)["frames"] = [frame(1, 1)]


def _balcony_above_frame(d):
    m(d)["floors"][2]["front_setback"]["value"] = 0.0
    m(d)["floors"][1].pop("terrace_pergola")
    bal = copy.deepcopy(m(d)["balconies"][0])
    bal["floor"]["value"] = 3
    m(d)["balconies"] = [bal]


def _canopy_into_balcony(d):
    m(d)["canopy"]["height"]["value"] = 3.45


def _balcony_rail_into_frame_post(d):
    m(d)["balconies"][0]["offset"]["value"] = 0.0
    m(d)["balconies"][0]["width"]["value"] = 5.0


def _louver_into_frame_post(d):
    m(d)["louvers"][0]["offset"]["value"] = 0.2


def _balcony_on_setback_floor(d):
    m(d)["balconies"][0]["floor"]["value"] = 3


def _two_balconies_same_floor(d):
    left = copy.deepcopy(m(d)["balconies"][0])
    left["offset"]["value"], left["width"]["value"] = 0.5, 1.5
    right = copy.deepcopy(left)
    right["offset"]["value"] = 3.0
    m(d)["balconies"] = [left, right]


def _shallow_yard_motorbikes(d):
    d["site"]["front_setback"]["value"] = 1.5
    m(d)["front_yard"]["car"]["value"] = False
    m(d)["canopy"]["depth"]["value"] = 1.0


def _roof_pergola_inverted(d):
    m(d)["roof"]["stair_head"]["depth"]["value"] = 11.5


def _transom_too_small(d):
    m(d)["floors"][0]["openings_front"][0]["transom_height"]["value"] = 0.03


def _window_too_narrow(d):
    m(d)["floors"][1]["openings_front"][0]["width"]["value"] = 0.15


def _crowded_louvers(d):
    m(d)["louvers"][0]["count"]["value"] = 30


def _shallow_terrace_pergola(d):
    m(d)["floors"][2]["front_setback"]["value"] = 0.2


def _id_collision(d):
    door = copy.deepcopy(m(d)["floors"][0]["openings_rear"][0])
    m(d)["floors"][0]["openings_rear"][0]["id"] = "D1_Frame"
    assert door["kind"] == "door"


CASES = [
    (_frame_floor1, "Canopy"),
    (_balcony_above_frame, "Balcony_F3"),
    (_canopy_into_balcony, "Balcony_F2"),
    (_balcony_rail_into_frame_post, "Frame_F2-2"),
    (_louver_into_frame_post, "Frame_F2-2"),
    (_balcony_on_setback_floor, "Balcony_F3"),
    (_two_balconies_same_floor, "Balcony_F2"),
    (_shallow_yard_motorbikes, "Prop_Motorbike_1"),
    (_roof_pergola_inverted, "Roof_Pergola"),
    (_transom_too_small, "Door_D1_"),
    (_window_too_narrow, "Window_W2_"),
    (_crowded_louvers, "Louver_F2_"),
    (_shallow_terrace_pergola, "Floor2_Terrace_Pergola"),
    (_id_collision, "Door_D1_Frame"),
]


@pytest.mark.parametrize(("mutate", "expected"), CASES, ids=[c[0].__name__ for c in CASES])
def test_invalid_geometry_rejected(modern_data, mutate, expected):
    mutate(modern_data)
    assert expected in messages(modern_data)


def test_fixture_geometry_is_clean(modern_data):
    parse_project(modern_data)


def test_terrace_pergola_without_terrace_rejected(modern_data):
    m(modern_data)["floors"][0]["terrace_pergola"] = P(True, None)
    assert "modern.floors[0].terrace_pergola" in messages(modern_data)

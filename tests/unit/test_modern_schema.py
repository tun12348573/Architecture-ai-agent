import copy

import pytest

from exterior_agent.domain.validate import (
    ProjectValidationError,
    parse_project,
    unresolved_assumptions,
)


def issues_for(data) -> list:
    with pytest.raises(ProjectValidationError) as exc:
        parse_project(data)
    return exc.value.issues


def paths(issues) -> set[str]:
    return {i.path for i in issues}


def floor(data, n):
    return data["modern"]["floors"][n - 1]


def test_modern_fixture_is_valid(modern_data):
    project = parse_project(modern_data)
    assert project.template == "modern_townhouse"
    assert len(project.modern.floors) == 3
    assert project.building is None
    assert "modern.wall_thickness" in unresolved_assumptions(project)


def test_m1_fixture_still_valid(demo_data):
    project = parse_project(demo_data)
    assert project.template == "basic_house"
    assert project.modern is None


def test_template_pairing_rules(modern_data, demo_data):
    both = copy.deepcopy(modern_data)
    both["building"] = demo_data["building"]
    assert "template" in paths(issues_for(both))
    old = copy.deepcopy(modern_data)
    old["schema_version"] = "1.0"
    assert "template" in paths(issues_for(old))
    basic_without_building = copy.deepcopy(demo_data)
    del basic_without_building["building"]
    assert "template" in paths(issues_for(basic_without_building))


def _five_floors(data, height):
    template = floor(data, 2)
    for _ in range(2):
        extra = copy.deepcopy(template)
        extra["openings_front"], extra["openings_rear"] = [], []
        extra["front_setback"]["value"] = 2.0
        extra.pop("terrace_pergola", None)
        data["modern"]["floors"].append(extra)
    for f in data["modern"]["floors"]:
        f["height"]["value"] = height


def test_height_limit_accepted(modern_data):
    _five_floors(modern_data, 4.44)  # 5 x 4.44 + stair head 2.8 = 25.0
    parse_project(modern_data)


def test_height_limit_rejected(modern_data):
    _five_floors(modern_data, 4.4404)  # 25.002
    assert "modern.floors" in paths(issues_for(modern_data))


def test_floor_count_limits(modern_data):
    _five_floors(modern_data, 3.3)
    modern_data["modern"]["floors"].append(copy.deepcopy(floor(modern_data, 5)))
    assert "modern.floors" in paths(issues_for(modern_data))


def test_floor1_setback_must_be_zero(modern_data):
    floor(modern_data, 1)["front_setback"]["value"] = 0.5
    floor(modern_data, 2)["front_setback"]["value"] = 0.5
    assert "modern.floors[0].front_setback" in paths(issues_for(modern_data))


def test_setbacks_non_decreasing(modern_data):
    floor(modern_data, 2)["front_setback"]["value"] = 2.5
    assert "modern.floors[2].front_setback" in paths(issues_for(modern_data))


def test_duplicate_opening_id_across_floors(modern_data):
    floor(modern_data, 2)["openings_front"][0]["id"] = "D1"
    assert "modern.floors[1].openings_front[0].id" in paths(issues_for(modern_data))


def test_opening_lintel_uses_floor_clear_height(modern_data):
    floor(modern_data, 2)["openings_front"][0]["height"]["value"] = 2.7  # 0.5 + 2.7 > 3.15 - 0.1
    assert "modern.floors[1].openings_front[0].height" in paths(issues_for(modern_data))


def test_balcony_out_of_lot_rejected(modern_data):
    modern_data["modern"]["balconies"][0]["depth"]["value"] = 4.6
    assert "modern.balconies[0].depth" in paths(issues_for(modern_data))


def test_balcony_floor_range(modern_data):
    modern_data["modern"]["balconies"][0]["floor"]["value"] = 1
    assert "modern.balconies[0].floor" in paths(issues_for(modern_data))


def test_car_needs_parking_and_depth(modern_data):
    garden = copy.deepcopy(modern_data)
    garden["modern"]["front_yard"]["kind"]["value"] = "garden"
    assert "modern.front_yard.car" in paths(issues_for(garden))
    shallow = copy.deepcopy(modern_data)
    shallow["site"]["front_setback"]["value"] = 4.4
    assert "modern.front_yard.car" in paths(issues_for(shallow))


def test_door_4leaf_rules(modern_data):
    door = floor(modern_data, 1)["openings_front"][0]
    door["sill"]["value"] = 0.1
    assert "modern.floors[0].openings_front[0].sill" in paths(issues_for(modern_data))
    door["sill"]["value"] = 0.0
    door["transom_height"]["value"] = 2.6
    assert "modern.floors[0].openings_front[0].transom_height" in paths(issues_for(modern_data))


def test_canopy_must_clear_ground_floor_openings(modern_data):
    modern_data["modern"]["canopy"]["height"]["value"] = 2.5  # door top is 2.6
    assert "modern.canopy.height" in paths(issues_for(modern_data))


def test_frame_floors_share_setback(modern_data):
    modern_data["modern"]["frames"][0]["to_floor"]["value"] = 3
    assert "modern.frames[0]" in paths(issues_for(modern_data))


def test_louvers_inside_facade(modern_data):
    modern_data["modern"]["louvers"][0]["width"]["value"] = 2.5  # 3.0 + 2.5 > 5.0 - 0.2
    assert "modern.louvers[0].width" in paths(issues_for(modern_data))


def test_stair_head_inside_roof(modern_data):
    modern_data["modern"]["roof"]["stair_head"]["width"]["value"] = 4.9
    assert "modern.roof.stair_head.width" in paths(issues_for(modern_data))


def test_gate_wider_than_site_rejected(modern_data):
    modern_data["modern"]["front_yard"]["gate_width"]["value"] = 5.5
    assert "modern.front_yard.gate_width" in paths(issues_for(modern_data))


def test_missing_modern_material_role(modern_data):
    del modern_data["materials"]["louver"]
    assert "materials.louver" in paths(issues_for(modern_data))


def test_flag_must_be_bool(modern_data):
    modern_data["modern"]["front_yard"]["car"]["value"] = 1
    assert any(p.startswith("modern.front_yard.car") for p in paths(issues_for(modern_data)))

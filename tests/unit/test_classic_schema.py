"""Neoclassical townhouse (style C) schema and parameter rules."""

import copy

import pytest

from exterior_agent.domain.validate import ProjectValidationError, parse_project


def paths(data) -> set[str]:
    with pytest.raises(ProjectValidationError) as exc:
        parse_project(data)
    return {i.path for i in exc.value.issues}


def front(data, floor, k):
    return data["classic"]["floors"][floor]["openings_front"][k]


def test_fixture_parses(classic_data):
    p = parse_project(classic_data)
    assert p.template == "neoclassical_townhouse"
    assert len(p.classic.floors) == 3
    assert p.body is p.classic


def test_body_is_modern_for_modern(modern_data):
    p = parse_project(modern_data)
    assert p.body is p.modern


def test_classic_needs_classic_block(classic_data, modern_data):
    classic_data["modern"] = modern_data["modern"]
    assert "template" in paths(classic_data)


def test_arch_taller_than_opening(classic_data):
    o = front(classic_data, 1, 0)
    o["width"]["value"], o["height"]["value"] = 1.4, 0.6
    assert "classic.floors[1].openings_front[0].height" in paths(classic_data)


def test_arch_crown_above_clear_height(classic_data):
    front(classic_data, 1, 0)["height"]["value"] = 3.3
    assert "classic.floors[1].openings_front[0].height" in paths(classic_data)


@pytest.mark.parametrize("pitch", [60.0, 20.0])
def test_pitch_range(classic_data, pitch):
    classic_data["classic"]["roof"]["pitch_deg"]["value"] = pitch
    assert "classic.roof.pitch_deg" in paths(classic_data)


def test_ridge_limit(classic_data):
    floors = classic_data["classic"]["floors"]
    floors.append(floors[-1])
    for f in floors:
        f["height"]["value"] = 6.0
    assert "classic.floors" in paths(classic_data)


def test_bay_side_choice(classic_data):
    classic_data["classic"]["bay"]["side"]["value"] = "middle"
    assert "classic.bay.side" in paths(classic_data)


def test_bay_past_front_boundary(classic_data):
    classic_data["classic"]["bay"]["projection"]["value"] = 4.5
    assert "classic.bay.projection" in paths(classic_data)


def test_opening_hits_column(classic_data):
    front(classic_data, 1, 0)["offset"]["value"] = 0.2  # left column: 0.14..0.50
    assert "classic.floors[1].openings_front[0]" in paths(classic_data)


def test_oculus_outside_gable(classic_data):
    classic_data["classic"]["roof"]["gable_front"]["oculus_radius"]["value"] = 2.0
    assert "classic.roof.gable_front.oculus_radius" in paths(classic_data)


def test_pediment_hits_opening_above(classic_data):
    classic_data["classic"]["bay"]["pediment"]["height"]["value"] = 2.0
    assert "classic.bay.pediment.height" in paths(classic_data)


def test_required_roles(classic_data):
    del classic_data["materials"]["roof_tiles"]
    assert "materials.roof_tiles" in paths(classic_data)


def test_metallic_bounds(classic_data):
    classic_data["materials"]["iron"]["value"]["metallic"] = 1.5
    assert "materials.iron.value.metallic" in paths(classic_data)


# ---- final-review fixes (M2d) ----
def bay_to_floor3(data, side="left"):
    bay = data["classic"]["bay"]
    bay["side"]["value"], bay["to_floor"]["value"], bay["pediment"] = side, 3, None
    return data


def test_opening_behind_pilaster(classic_data):
    front(classic_data, 2, 0)["offset"]["value"] = 0.25  # pilaster is 0.4 wide
    assert "classic.floors[2].openings_front[0].offset" in paths(classic_data)


def test_bay_wall_opening_touches_edge(classic_data):
    bay_to_floor3(classic_data, "right")
    front(classic_data, 2, 1)["offset"]["value"] = 2.4  # right bay starts at 2.4
    assert "classic.floors[2].openings_front[1]" in paths(classic_data)


def test_opening_straddles_bay(classic_data):
    bay_to_floor3(classic_data)
    front(classic_data, 2, 0)["offset"]["value"] = 2.0  # 2.0..3.2 across the edge at 2.6
    front(classic_data, 2, 1)["offset"]["value"] = 3.5
    front(classic_data, 2, 1)["width"]["value"] = 0.9
    assert "classic.floors[2].openings_front[0]" in paths(classic_data)


def test_bay_wall_balcony_projection(classic_data):
    bay_to_floor3(classic_data)
    classic_data["classic"]["bay"]["projection"]["value"] = 3.5
    front(classic_data, 2, 0)["balcony"]["projection"]["value"] = 1.0  # > 4.0 - 3.5
    assert "classic.floors[2].openings_front[0].balcony.projection" in paths(classic_data)


def test_narrow_bay_with_columns(classic_data):
    classic_data["classic"]["bay"]["width"]["value"] = 0.6
    assert "classic.bay.width" in paths(classic_data)


def test_balcony_over_pediment(classic_data):
    front(classic_data, 2, 0)["balcony"]["kind"] = "balustrade"
    assert "classic.floors[2].openings_front[0].balcony" in paths(classic_data)


def test_classic_car_checked(classic_data):
    classic_data["classic"]["front_yard"]["car"]["value"] = True
    assert "classic.front_yard.car" in paths(classic_data)


def test_props_role_required(classic_data):
    yard = classic_data["classic"]["front_yard"]
    yard["kind"]["value"], yard["motorbikes"]["value"] = "parking", 2
    del classic_data["materials"]["props"]
    assert "materials.props" in paths(classic_data)


def test_rear_balcony_and_hood_rejected(classic_data):
    rear = classic_data["classic"]["floors"][0]["openings_rear"][1]
    rear["balcony"] = copy.deepcopy(front(classic_data, 1, 1)["balcony"])
    rear["hood"] = copy.deepcopy(front(classic_data, 1, 1)["hood"])
    issues = paths(classic_data)
    assert "classic.floors[0].openings_rear[1].balcony" in issues
    assert "classic.floors[0].openings_rear[1].hood" in issues


def test_arch_too_short_for_frame(classic_data):
    front(classic_data, 2, 1)["height"]["value"] = 0.65  # w/2 = 0.55, frame needs 2 x 0.06
    assert "classic.floors[2].openings_front[1].height" in paths(classic_data)


def test_door_too_low(classic_data):
    front(classic_data, 0, 0)["height"]["value"] = 1.2  # door leaves only 0.3 m tall
    assert "classic.floors[0].openings_front[0].height" in paths(classic_data)


def test_facade_outside_lot_flagged(classic_data):
    from exterior_agent.geometry.modern_checks import check_classic_geometry

    p = parse_project(classic_data)
    bay = p.classic.bay
    p.classic.bay = bay.model_copy(update={"width": bay.width.model_copy(update={"value": 0.6})})
    assert any("Bay_Columns" in i.message for i in check_classic_geometry(p))

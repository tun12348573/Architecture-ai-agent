"""Neoclassical townhouse (style C) schema and parameter rules."""

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
    front(classic_data, 1, 0)["offset"]["value"] = 0.2  # left column spans 0.05..0.41
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

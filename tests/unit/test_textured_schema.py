import pytest

from exterior_agent.domain.validate import ProjectValidationError, parse_project


def P(v, unit=None):
    return {"value": v, "unit": unit, "source": "test", "source_ref": "t", "status": "confirmed"}


def paths(data) -> set[str]:
    with pytest.raises(ProjectValidationError) as exc:
        parse_project(data)
    return {i.path for i in exc.value.issues}


def test_fixture_uses_catalog_assets(modern_data):
    p = parse_project(modern_data)
    assert p.materials.wall.value.texture == "beige_wall_001"
    assert p.world.hdri.value == "kloofendal_48d_partly_cloudy_puresky"
    assert [m.value for m in p.modern.roof.garden.plant_models] == ["shrub_01", "shrub_02"]


def test_unknown_texture_rejected(modern_data):
    modern_data["materials"]["wall"]["value"]["texture"] = "no_such_texture"
    assert "materials.wall.value.texture" in paths(modern_data)


def test_hdri_must_be_hdri_asset(modern_data):
    modern_data["world"]["hdri"]["value"] = "painted_plaster_wall"
    assert "world.hdri" in paths(modern_data)


def test_plant_model_must_be_model_asset(modern_data):
    modern_data["modern"]["roof"]["garden"]["plant_models"][0]["value"] = "farm_soil"
    assert "modern.roof.garden.plant_models[0]" in paths(modern_data)


@pytest.mark.parametrize(("key", "value"), [("strength", 0.0), ("rotation_deg", 360.0)])
def test_world_ranges(modern_data, key, value):
    modern_data["world"][key]["value"] = value
    assert f"world.{key}" in paths(modern_data)


def test_world_and_textures_only_for_modern(demo_data):
    with_world = dict(demo_data)
    with_world["world"] = {"hdri": P("kloofendal_48d_partly_cloudy_puresky"),
                           "strength": P(1.0), "rotation_deg": P(0.0)}  # fmt: skip
    assert "template" in paths(with_world)
    demo_data["materials"]["wall"]["value"]["texture"] = "painted_plaster_wall"
    assert "template" in paths(demo_data)


def test_m1_fixture_still_valid(demo_data):
    assert parse_project(demo_data).world is None

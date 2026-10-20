"""M2c schema: street context, ground-floor cladding and glass transmission."""

import copy

import pytest

from exterior_agent.domain.validate import ProjectValidationError, parse_project


def P(v, unit=None):
    return {"value": v, "unit": unit, "source": "test", "source_ref": "t", "status": "confirmed"}


def M(color, texture=None, **extra):
    value = {"base_color": color, "roughness": 0.8, **extra}
    if texture:
        value["texture"] = texture
    return P(value)


CONTEXT = {
    "front": P("road"),
    "sidewalk_width": P(3.0, "m"),
    "road_width": P(7.0, "m"),
    "neighbours": {"per_side": P(2, "count"), "seed": P(7, "count")},
    "street_lamps": P(True),
    "street_trees": P(True),
    "pots": P(True),
    "models": {
        "tree": P("island_tree_02"),
        "lamp": P("street_lamp_01"),
        "pot": P("potted_plant_02"),
    },
}
CONTEXT_MATERIALS = {
    "asphalt": M([1, 1, 1], "clean_asphalt"),
    "sidewalk": M([1, 1, 1], "concrete_pavement_02"),
    "kerb": M([1, 1, 1], "concrete"),
    "road_marking": M([0.9, 0.9, 0.85]),
    "neighbour_wall": M([1, 1, 1], "beige_wall_001"),
    "neighbour_glass": M([0.05, 0.06, 0.07]),
}


def add_context(data: dict) -> dict:
    data["context"] = copy.deepcopy(CONTEXT)
    data["materials"].update(copy.deepcopy(CONTEXT_MATERIALS))
    data["modern"]["cladding"] = {"zone": P("ground_front"), "thickness": P(0.02, "m")}
    data["materials"]["cladding"] = M([1, 1, 1], "brick_wall_09")
    return data


@pytest.fixture
def ctx_data(modern_data):
    return add_context(modern_data)


def paths(data) -> set[str]:
    with pytest.raises(ProjectValidationError) as exc:
        parse_project(data)
    return {i.path for i in exc.value.issues}


def test_valid_context_parses(ctx_data):
    p = parse_project(ctx_data)
    assert p.context.front.value == "road"
    assert p.context.neighbours.per_side.value == 2
    assert p.modern.cladding.thickness.value == 0.02


def test_context_requires_modern(demo_data):
    demo_data["context"] = CONTEXT
    assert "template" in paths(demo_data)


def test_front_choice(ctx_data):
    ctx_data["context"]["front"]["value"] = "river"
    assert "context.front" in paths(ctx_data)


def test_per_side_range(ctx_data):
    ctx_data["context"]["neighbours"]["per_side"]["value"] = 5
    assert "context.neighbours.per_side" in paths(ctx_data)


def test_context_roles_required(ctx_data):
    del ctx_data["materials"]["asphalt"]
    assert "materials.asphalt" in paths(ctx_data)


def test_neighbour_wall_required_with_neighbours(ctx_data):
    del ctx_data["materials"]["neighbour_wall"]
    assert "materials.neighbour_wall" in paths(ctx_data)
    ctx_data["context"]["neighbours"] = None
    parse_project(ctx_data)  # no neighbours → role not needed


def test_cladding_zone(ctx_data):
    ctx_data["modern"]["cladding"]["zone"]["value"] = "rear"
    assert "modern.cladding.zone" in paths(ctx_data)


def test_cladding_role_required(ctx_data):
    del ctx_data["materials"]["cladding"]
    assert "materials.cladding" in paths(ctx_data)


def test_context_models_kind(ctx_data):
    ctx_data["context"]["models"]["tree"]["value"] = "concrete"
    assert "context.models.tree" in paths(ctx_data)


def test_transmission_bounds(ctx_data):
    ctx_data["materials"]["window_glass"]["value"]["transmission"] = 1.5
    assert "materials.window_glass.value.transmission" in paths(ctx_data)


def test_transmission_defaults_to_zero(modern_data):
    assert parse_project(modern_data).materials.wall.value.transmission == 0.0


def test_cladding_below_opening_head(ctx_data):
    # canopy 2.65 clears the 2.6 m door, but leaves no 0.10 m cladding lintel above it
    ctx_data["modern"]["canopy"]["height"]["value"] = 2.65
    issues = paths(ctx_data)
    assert "modern.cladding" in issues
    assert "modern.canopy.height" not in issues

"""Placement of CC0 models: pots on balconies/terraces, street trees, lamps, roof garden."""

import pytest

from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.geometry.context_assets import TREE_BASE_SCALE, context_asset_specs
from exterior_agent.geometry.modern_massing import (
    floor_base_z,
    floor_front_y,
    roof_plant_positions,
)
from exterior_agent.geometry.scene_plan import build_scene_plan


@pytest.fixture
def project(modern_data):
    return parse_project(modern_data)


def by_prefix(specs, prefix):
    return [s for s in specs if s.name.startswith(prefix)]


def test_pots_on_slabs(project):
    m = project.modern
    pots = by_prefix(context_asset_specs(project), "Pot_")
    assert pots and all(s.collection == "Plants" and s.model == "potted_plant_02" for s in pots)
    areas = []  # (x0, x1, y0, y1, z) of every floor a pot may stand on
    for bal in m.balconies:
        n = bal.floor.value
        x0 = -m.footprint_width.value / 2 + bal.offset.value
        yf = floor_front_y(project, n)
        areas.append((x0, x0 + bal.width.value, yf - bal.depth.value, yf, floor_base_z(m, n)))
    for n in range(1, len(m.floors)):
        y0, y1 = floor_front_y(project, n), floor_front_y(project, n + 1)
        if y1 > y0:
            w = m.footprint_width.value / 2
            top = floor_base_z(m, n) + m.floors[n - 1].height.value
            areas.append((-w, w, y0, y1, top))
    for s in pots:
        x, y, z = s.location
        assert any(
            a[0] + 0.3 <= x <= a[1] - 0.3
            and a[2] + 0.3 <= y <= a[3] - 0.3
            and z == pytest.approx(a[4])
            for a in areas
        ), s.name
    assert len(pots) == 2 * len(areas)


def test_trees_and_lamps_clear_of_lot_front(modern_data):
    for front in ("road", "park"):
        modern_data["context"]["front"]["value"] = front
        p = parse_project(modern_data)
        half = p.site.width.value / 2
        specs = context_asset_specs(p)
        street = by_prefix(specs, "Tree_") + by_prefix(specs, "Lamp_")
        assert by_prefix(specs, "Tree_") and by_prefix(specs, "Lamp_"), front
        for s in street:
            assert abs(s.location[0]) >= half + 1 and s.location[1] < 0, (front, s.name)
            assert s.collection == "Context"


def test_assets_deterministic(project):
    assert context_asset_specs(project) == context_asset_specs(project)


def test_tree_scale_range(project):
    # island_tree_02 is ~3.4 m tall: street trees are scaled to ~5-7 m, varied by ±15 %
    for s in by_prefix(context_asset_specs(project), "Tree_"):
        assert 0.85 * TREE_BASE_SCALE <= s.scale <= 1.15 * TREE_BASE_SCALE


def test_flags_switch_assets_off(modern_data):
    for flag in ("pots", "street_trees", "street_lamps"):
        modern_data["context"][flag]["value"] = False
    assert context_asset_specs(parse_project(modern_data)) == []


def test_yard_tree_only_for_garden(modern_data):
    assert not by_prefix(context_asset_specs(parse_project(modern_data)), "Tree_Yard")
    modern_data["modern"]["front_yard"]["kind"]["value"] = "garden"
    p = parse_project(modern_data)
    (tree,) = by_prefix(context_asset_specs(p), "Tree_Yard")
    x, y, _ = tree.location
    half, fs = p.site.width.value / 2, p.site.front_setback.value
    assert -half < x < half and 0 < y < fs
    assert abs(x) >= 1.0  # beside, not in front of, the entrance walkway


def test_roof_garden_denser(project):
    m = project.modern
    inner = m.footprint_width.value - 2 * m.roof.parapet_thickness.value
    assert len(roof_plant_positions(project)) == round(inner / 0.8)


def test_plan_assets_cover_context(project):
    plan = build_scene_plan(project, resolve_render("preview"))
    names = {a["name"] for a in plan["assets"]}
    assert {s.name for s in context_asset_specs(project)} <= names
    assert any(n.startswith("Plant_Roof_") for n in names)
    tree = next(a for a in plan["assets"] if a["name"].startswith("Tree_"))
    assert tree["model"]["path"].startswith("materials/island_tree_02/")


def test_smoke_plan_has_no_assets(project):
    assert "assets" not in build_scene_plan(project, resolve_render("smoke"))

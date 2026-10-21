"""Neoclassical template built by real Blender: components, real arched holes, GLB, textures."""

import copy
import json
from dataclasses import replace

import pytest

from exterior_agent.assets.catalog import load_catalog
from exterior_agent.assets.fetch import cache_dir, verify_cached
from exterior_agent.blender.invoke import find_blender
from exterior_agent.domain.classic_rules import OCULUS_HEIGHT, gable_height
from exterior_agent.domain.project import CANONICAL_CAMERA_IDS
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.runtime.delivery import validate_png, verify_delivery
from exterior_agent.runtime.runner import BuildOptions, run_build
from tests.integration.conftest import REPO_ROOT, inspect

pytestmark = pytest.mark.blender
CLASSIC = json.loads(
    (REPO_ROOT / "examples" / "neoclassical_townhouse" / "project.json").read_text(encoding="utf-8")
)
NAMES = {"Bay_Columns", "Gable_Front_Ornament", "Roof_Tiles_L", "Balcony_Bay_Iron", "Cornice_F3",
         "Door_D1", "Window_W6_Glass", "Gate_Pier_L"}  # fmt: skip


@pytest.fixture(scope="module")
def built(blender_cmd, tmp_path_factory):
    out = tmp_path_factory.mktemp("classic out")
    project = parse_project(copy.deepcopy(CLASSIC))
    opts = BuildOptions(out_dir=out, render=resolve_render("smoke"), blender=find_blender())
    outcome = run_build(project, opts)
    assert outcome.status == "completed", outcome.message
    return project, outcome.revision_dir


def test_classic_build_completes(built):
    _, rev = built
    for cam in CANONICAL_CAMERA_IDS:
        assert validate_png(rev / "images" / f"{cam}.png", 128, 72) is None, cam
    assert verify_delivery(rev) == []


def test_named_components_present(blender_cmd, built, tmp_path):
    _, rev = built
    objects = inspect(blender_cmd, tmp_path, blend=rev / "model.blend")["objects"]
    assert NAMES <= set(objects)


def _rays(project):
    m, yf = project.classic, project.site.front_setback.value
    w2 = m.footprint_width.value / 2
    d3 = m.floors[1].openings_front[0]
    x0 = -w2 + d3.offset.value
    z = m.floors[0].height.value + d3.sill.value + d3.height.value - d3.width.value / 2
    top = sum(f.height.value for f in m.floors)
    zoc, r = top + OCULUS_HEIGHT * gable_height(m), m.roof.gable_front.oculus_radius.value
    rays = []
    for obj, x, zz, hit in (
        ("Floor2_Wall_Front", x0 + d3.width.value / 2, z, False),  # through the arch
        ("Floor2_Wall_Front", x0 - 0.05, z, True),
        ("Gable_Front", 0.0, zoc, False),  # through the oculus
        ("Gable_Front", r + 0.08, zoc, True),
    ):
        ray = {"object": obj, "origin": [x, yf - 0.1, zz], "direction": [0, 1, 0], "distance": 0.5}
        rays.append((ray, hit))
    return rays


def test_arched_openings_raycast(blender_cmd, built, tmp_path):
    project, rev = built
    rays = _rays(project)
    report = inspect(blender_cmd, tmp_path, blend=rev / "model.blend", rays=[r for r, _ in rays])
    assert report["rays"] == [hit for _, hit in rays]


def test_glb_reimport(blender_cmd, built, tmp_path):
    _, rev = built
    report = inspect(blender_cmd, tmp_path, glb=rev / "model.glb")
    assert NAMES <= set(report["objects"])
    assert report["material_inputs"]["MAT_Iron"]["metallic"] >= 0.6


def test_textured_roof_tiles(blender_cmd, tmp_path_factory):
    catalog, cache = load_catalog(), cache_dir()
    if any(verify_cached(cache, a) for a in catalog.assets):
        pytest.skip(f"asset cache {cache} incomplete: run `exterior-agent assets fetch`")
    out = tmp_path_factory.mktemp("classic textured")
    tiny = replace(resolve_render("preview"), width=128, height=72)
    opts = BuildOptions(out_dir=out, render=tiny, blender=find_blender())
    outcome = run_build(parse_project(copy.deepcopy(CLASSIC)), opts)
    assert outcome.status == "completed", outcome.message
    rev = outcome.revision_dir
    assert (rev / "materials" / "clay_roof_tiles").is_dir()
    licences = json.loads((rev / "materials" / "LICENSES.json").read_text(encoding="utf-8"))
    assert "clay_roof_tiles" in {e["id"] for e in licences}

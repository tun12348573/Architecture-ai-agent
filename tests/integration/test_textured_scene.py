import copy
import json
import shutil
from dataclasses import replace

import pytest

from exterior_agent.assets.catalog import load_catalog
from exterior_agent.assets.fetch import cache_dir, verify_cached
from exterior_agent.blender.invoke import find_blender
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.modern_massing import massing_objects
from exterior_agent.runtime.delivery import read_glb
from exterior_agent.runtime.runner import BuildOptions, run_build
from tests.integration.conftest import REPO_ROOT, inspect

pytestmark = pytest.mark.blender
MODERN = json.loads(
    (REPO_ROOT / "examples" / "modern_townhouse" / "project.json").read_text(encoding="utf-8")
)
TINY_PREVIEW = replace(resolve_render("preview"), width=128, height=72)


@pytest.fixture(scope="module")
def textured(blender_cmd, tmp_path_factory):
    catalog, cache = load_catalog(), cache_dir()
    if any(verify_cached(cache, a) for a in catalog.assets):
        pytest.skip(f"asset cache {cache} incomplete: run `exterior-agent assets fetch`")
    out = tmp_path_factory.mktemp("textured out")
    project = parse_project(copy.deepcopy(MODERN))
    options = BuildOptions(out_dir=out, render=TINY_PREVIEW, blender=find_blender())
    outcome = run_build(project, options)
    assert outcome.status == "completed", outcome.message
    return project, outcome.revision_dir


def test_images_relative_and_present(blender_cmd, textured, tmp_path):
    _, rev = textured
    report = inspect(blender_cmd, tmp_path, blend=rev / "model.blend")
    images = report["images"]
    paths = [i["filepath"].replace("\\", "/") for i in images]  # Windows stores //materials\...
    assert images and all(p.startswith("//materials/") for p in paths), paths
    assert all(i["exists"] for i in images)
    assert report["world_nodes"] and "TEX_ENVIRONMENT" in report["world_nodes"]
    assert report["material_inputs"]["MAT_Wall"]["base_color_from"] == "TEX_IMAGE"


def test_plants_in_roof_planter(blender_cmd, textured, tmp_path):
    project, rev = textured
    planter = next(o for o in massing_objects(project) if o.name == "Planter_Roof_1")
    lo, hi = planter.mesh.bounds()
    objects = inspect(blender_cmd, tmp_path, blend=rev / "model.blend")["objects"]
    plants = {n: o for n, o in objects.items() if n.startswith("Plant_Roof_")}
    assert len(plants) == 3
    for name, entry in plants.items():
        assert "Roof" in entry["collections"], name
        assert entry["bbox_min"][2] == pytest.approx(hi[2], abs=0.05), name
        cx = (entry["bbox_min"][0] + entry["bbox_max"][0]) / 2
        cy = (entry["bbox_min"][1] + entry["bbox_max"][1]) / 2
        assert lo[0] - TOL < cx < hi[0] + TOL and lo[1] - 0.3 < cy < hi[1] + 0.3, name


def test_glb_carries_textures(textured):
    _, rev = textured
    doc = read_glb(rev / "model.glb")
    assert doc.get("images")
    wall = next(m for m in doc["materials"] if m["name"] == "MAT_Wall")
    assert "baseColorTexture" in wall["pbrMetallicRoughness"]


def test_revision_is_portable(blender_cmd, textured, tmp_path):
    _, rev = textured
    moved = tmp_path / "moved copy"
    shutil.copytree(rev, moved)
    report = inspect(blender_cmd, tmp_path, blend=moved / "model.blend")
    assert all(i["exists"] for i in report["images"])


def test_hdri_scene_uses_agx_and_softer_sun(blender_cmd, textured, tmp_path):
    _, rev = textured
    report = inspect(blender_cmd, tmp_path, blend=rev / "model.blend")
    assert report["view_transform"] == "AgX"
    plan = json.loads((rev / "scene_plan.json").read_text(encoding="utf-8"))
    assert plan["sun"]["strength"] < 3.0  # the HDRI already contains the sun

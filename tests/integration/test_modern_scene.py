import copy
import json

import pytest

from exterior_agent.blender.invoke import find_blender
from exterior_agent.domain.project import CANONICAL_CAMERA_IDS
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import TOL, parse_project
from exterior_agent.geometry.modern_massing import massing_objects
from exterior_agent.runtime.delivery import validate_png, verify_delivery
from exterior_agent.runtime.runner import BuildOptions, run_build
from tests.integration.conftest import REPO_ROOT, inspect

pytestmark = pytest.mark.blender
SMOKE = resolve_render("smoke")
MODERN = json.loads(
    (REPO_ROOT / "examples" / "modern_townhouse" / "project.json").read_text(encoding="utf-8")
)


def options(out) -> BuildOptions:
    return BuildOptions(out_dir=out, render=SMOKE, blender=find_blender())


@pytest.fixture(scope="module")
def built(blender_cmd, tmp_path_factory):
    out = tmp_path_factory.mktemp("modern out")
    project = parse_project(copy.deepcopy(MODERN))
    outcome = run_build(project, options(out))
    assert outcome.status == "completed", outcome.message
    return project, outcome.revision_dir


def _wall_rays(project):
    """+Y rays through each opening centre (expect miss) and 5 cm beside it (expect hit)."""
    boxes = {o.name: o.empty_box for o in massing_objects(project) if o.mesh is None}
    rays, expected = [], []
    for n, floor in enumerate(project.modern.floors, start=1):
        for side in ("front", "rear"):
            wall = f"Floor{n}_Wall_{side.capitalize()}"
            for o in getattr(floor, f"openings_{side}"):
                lo, hi = boxes[f"Opening_{o.id}"]
                cz = (lo[2] + hi[2]) / 2
                for x, hit in (((lo[0] + hi[0]) / 2, False), (lo[0] - 0.05, True)):
                    origin = [x, lo[1] - 0.1, cz]
                    rays.append(
                        {"object": wall, "origin": origin, "direction": [0, 1, 0], "distance": 0.4}
                    )
                    expected.append(hit)
    return rays, expected


def test_modern_build_completes(built):
    _, rev = built
    for cam in CANONICAL_CAMERA_IDS:
        assert validate_png(rev / "images" / f"{cam}.png", 128, 72) is None, cam
    assert verify_delivery(rev) == []


def test_blend_objects_collections_and_uvs(blender_cmd, built, tmp_path):
    project, rev = built
    plan = json.loads((rev / "scene_plan.json").read_text(encoding="utf-8"))
    rays, expected = _wall_rays(project)
    report = inspect(blender_cmd, tmp_path, blend=rev / "model.blend", rays=rays)
    objects = report["objects"]
    for spec in plan["objects"]:
        entry = objects[spec["name"]]
        assert spec["collection"] in entry["collections"], spec["name"]
        if spec["type"] == "MESH":
            assert entry["uv_layers"] == 1, spec["name"]
    wall = next(o for o in massing_objects(project) if o.name == "Floor3_Wall_Front")
    lo, hi = wall.mesh.bounds()
    assert objects["Floor3_Wall_Front"]["bbox_min"] == pytest.approx(list(lo), abs=TOL)
    assert objects["Floor3_Wall_Front"]["bbox_max"] == pytest.approx(list(hi), abs=TOL)
    assert report["rays"] == expected


def test_glb_reimport(blender_cmd, built, tmp_path):
    _, rev = built
    glb = inspect(blender_cmd, tmp_path, glb=rev / "model.glb")["objects"]
    blend = inspect(blender_cmd, tmp_path, blend=rev / "model.blend")["objects"]
    for name in ("Floor1_Wall_Front", "Balcony_F2", "Frame_F2-2", "StairHead"):
        assert glb[name]["bbox_min"] == pytest.approx(blend[name]["bbox_min"], abs=TOL), name
        assert glb[name]["bbox_max"] == pytest.approx(blend[name]["bbox_max"], abs=TOL), name


def test_changed_parameters_rebuild(blender_cmd, built, tmp_path):
    _, first_rev = built
    data = copy.deepcopy(MODERN)
    m = data["modern"]
    m["balconies"] = []
    extra = copy.deepcopy(m["floors"][2])
    extra["openings_front"][0]["id"] = "W6"
    extra["openings_rear"][0]["id"] = "W7"
    m["floors"].append(extra)
    outcome = run_build(parse_project(data), options(first_rev.parent.parent))
    assert outcome.status == "completed", outcome.message
    assert outcome.revision_dir != first_rev
    objects = inspect(blender_cmd, tmp_path, blend=outcome.revision_dir / "model.blend")["objects"]
    assert "Balcony_F2" not in objects and "Floor4_Wall_Front" in objects
    assert verify_delivery(first_rev) == []

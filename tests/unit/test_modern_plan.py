import hashlib
import itertools
import json

import pytest

from exterior_agent.domain.project import CANONICAL_CAMERA_IDS
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.geometry.cameras import fit_cameras, project_point
from exterior_agent.geometry.scene_plan import build_scene_plan, modern_bounds
from exterior_agent.runtime.files import canonical_json

SMOKE = resolve_render("smoke")
GOLDEN = {
    "smoke": "a4b3f08d4dbdf3af336bca8db463dba0eb6797cd85f31a0e42d74b4f258b062e",
    "preview": "c4f2b1a127eda2d62ff3f9bfe95220e2df0191d2df1224bbe044a19b38a5865c",
}
EXPECTED = (
    {f"Floor{n}_Wall_{s}" for n in (1, 2, 3) for s in ("Front", "Rear", "Left", "Right")}
    | {f"Floor{n}_Slab" for n in (1, 2, 3)}
    | {f"Opening_{i}" for i in ("D1", "D2", "W1", "W2", "W3", "W4", "W5")}
    | {"Floor2_Terrace_Rail", "Floor2_Terrace_Pergola", "Parapet", "StairHead"}
    | {"Planter_Roof_1", "Roof_Pergola", "Balcony_F2", "Balcony_F2_Rail", "Frame_F2-2"}
    | {f"Louver_F2_{k}" for k in range(1, 7)}
    | {"Canopy", "Cladding_F1_Front", "Door_D1_Frame", "Door_D1_Glass", "Door_D2"}
    | {f"Window_W{k}_{part}" for k in range(1, 6) for part in ("Frame", "Glass")}
    | {"Yard_Front", "Yard_Rear", "Site_Context", "Fence_Left", "Fence_Right", "Gate"}
    | {"Sidewalk_Front", "Kerb_Front", "Road", "Road_Marking", "Sidewalk_Opposite"}
    | {"Ground_Left", "Ground_Right"}
    | {f"Backdrop_{i}" for i in ("D1", "W1", "W2", "W3", "W4", "W5")}
    | {f"Neighbour_{s}{k}{g}" for s in "LR" for k in (1, 2) for g in ("", "_Glass")}
)


@pytest.mark.parametrize("profile", ["smoke", "preview"])
def test_m1_plan_hash_unchanged(demo_data, profile):
    plan = build_scene_plan(parse_project(demo_data), resolve_render(profile))
    assert hashlib.sha256(canonical_json(plan).encode()).hexdigest() == GOLDEN[profile]


@pytest.fixture
def plan(modern_data):
    return build_scene_plan(parse_project(modern_data), SMOKE)


def test_modern_plan_names_unique_and_expected(plan):
    names = [o["name"] for o in plan["objects"]]
    assert len(names) == len(set(names))
    assert set(names) == EXPECTED


def test_every_mesh_has_uvs(plan):
    for o in plan["objects"]:
        if o["type"] == "MESH":
            assert len(o["uvs"]) == len(o["faces"]), o["name"]
            assert all(len(uv) == len(f) for uv, f in zip(o["uvs"], o["faces"], strict=True))


def test_materials_referenced_and_defined(plan):
    defined = {m["name"] for m in plan["materials"]}
    used = {o["material"] for o in plan["objects"] if o["type"] == "MESH"}
    assert used == defined
    assert "MAT_Glass" in defined and "MAT_Window_Glass" not in defined


def test_cameras_frame_the_modern_house(modern_data, plan):
    assert [c["id"] for c in plan["cameras"]] == list(CANONICAL_CAMERA_IDS)
    building, site = modern_bounds(parse_project(modern_data))
    assert building[1][2] == pytest.approx(13.0)  # stair head top
    assert building[0][1] == pytest.approx(3.3)  # canopy / balcony project to y = 3.3
    for pose in fit_cameras(building, site):
        target = site if pose.id in ("09_top", "10_aerial") else building
        for corner in itertools.product(*zip(*target, strict=True)):
            x, y, depth = project_point(pose, corner)
            assert depth > 0 and max(abs(x), abs(y)) <= 0.8 + 1e-6, pose.id


def test_modern_minimal_config(modern_data):
    m = modern_data["modern"]
    m["balconies"], m["frames"], m["louvers"] = [], [], []
    del m["canopy"]
    del m["roof"]["garden"]
    m["floors"][1].pop("terrace_pergola")
    m["front_yard"]["kind"]["value"] = "garden"
    m["front_yard"]["car"]["value"] = False
    m["front_yard"]["motorbikes"]["value"] = 0
    plan = build_scene_plan(parse_project(modern_data), SMOKE)
    names = {o["name"] for o in plan["objects"]}
    assert not names & {"Canopy", "Frame_F2-2", "Balcony_F2", "Roof_Pergola", "Prop_Car"}
    assert "Floor2_Terrace_Rail" in names and "Floor2_Terrace_Pergola" not in names


def _round(node):
    if isinstance(node, float):
        return round(node, 9) + 0.0
    if isinstance(node, list):
        return [_round(v) for v in node]
    if isinstance(node, dict):
        return {k: _round(v) for k, v in node.items()}
    return node


def test_modern_mm_equals_m(modern_data):
    in_m = build_scene_plan(parse_project(json.loads(json.dumps(modern_data))), SMOKE)

    def to_mm(node):
        if isinstance(node, dict):
            if node.get("unit") == "m":
                node["value"] = node["value"] * 1000
                node["unit"] = "mm"
            for v in node.values():
                to_mm(v)
        elif isinstance(node, list):
            for v in node:
                to_mm(v)

    to_mm(modern_data)
    in_mm = build_scene_plan(parse_project(modern_data), SMOKE)
    assert canonical_json(_round(in_mm)) == canonical_json(_round(in_m))

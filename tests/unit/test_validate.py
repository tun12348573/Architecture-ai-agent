import json

import pytest

from exterior_agent.domain.units import LENGTH_UNITS
from exterior_agent.domain.validate import (
    ProjectValidationError,
    load_project,
    parse_project,
    unresolved_assumptions,
)


def issues_for(data) -> list:
    with pytest.raises(ProjectValidationError) as exc:
        parse_project(data)
    return exc.value.issues


def paths(issues) -> set[str]:
    return {i.path for i in issues}


def opening(data, opening_id):
    return next(o for o in data["building"]["openings"] if o["id"] == opening_id)


def test_demo_fixture_is_valid(demo_data):
    project = parse_project(demo_data)
    assert project.building.wall_height.value == 3.6
    unresolved = unresolved_assumptions(project)
    assert "building.wall_thickness" in unresolved
    assert "building.openings[0].width" in unresolved
    assert "materials.wall" in unresolved
    assert "site.width" not in unresolved


def test_missing_field_reported_with_path(demo_data):
    del demo_data["building"]["wall_height"]
    assert "building.wall_height" in paths(issues_for(demo_data))


def test_non_finite_and_negative_rejected(demo_data):
    demo_data["site"]["width"]["value"] = float("nan")
    demo_data["building"]["footprint_depth"]["value"] = -1
    found = paths(issues_for(demo_data))
    assert any(p.startswith("site.width") for p in found)
    assert any(p.startswith("building.footprint_depth") for p in found)


def test_zero_length_rejected_except_offset_and_sill(demo_data):
    assert opening(demo_data, "D01")["sill"]["value"] == 0.0
    demo_data["building"]["wall_height"]["value"] = 0
    assert "building.wall_height" in paths(issues_for(demo_data))


def test_unknown_unit_rejected(demo_data):
    demo_data["site"]["depth"]["unit"] = "yd"
    assert any(p.startswith("site.depth") for p in paths(issues_for(demo_data)))


def test_footprint_depth_must_fit_site(demo_data):
    demo_data["building"]["footprint_depth"]["value"] = 12.5
    assert any(p.startswith("site") for p in paths(issues_for(demo_data)))


def test_footprint_width_must_fit_site(demo_data):
    demo_data["building"]["footprint_width"]["value"] = 4.6
    assert any(p.startswith("site") for p in paths(issues_for(demo_data)))


def test_unsupported_m1_features(demo_data):
    demo_data["building"]["floors"]["value"] = 2
    demo_data["building"]["roof"]["type"]["value"] = "gable"
    demo_data["input_mode"] = "cad"
    found = issues_for(demo_data)
    assert len([i for i in found if "not supported in M1" in i.message]) == 3


def _rear_windows_with_gap(data, gap):
    # D02 at rear: offset 0.5 width 0.9 -> ends at 1.4; W02 starts after `gap`.
    opening(data, "W02")["offset"]["value"] = 1.4 + gap


def test_opening_on_limits_accepted(demo_data):
    opening(demo_data, "D01")["offset"]["value"] = 0.2  # == wall thickness
    w01 = opening(demo_data, "W01")
    w01["sill"]["value"] = 2.1
    w01["height"]["value"] = 1.4  # top 3.5 == 3.6 - 0.10
    _rear_windows_with_gap(demo_data, 0.10)
    parse_project(demo_data)


def _set(data, opening_id, **values):
    for key, value in values.items():
        opening(data, opening_id)[key]["value"] = value


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: _set(d, "D01", offset=0.198),
        lambda d: _set(d, "W01", sill=2.102, height=1.4),  # top 3.502 > 3.5
        lambda d: _set(d, "W01", width=4.5 - 0.2 - 2.3 + 0.002),
        lambda d: _rear_windows_with_gap(d, 0.098),
        lambda d: _set(d, "D01", sill=0.3),
        lambda d: _set(d, "W01", sill=0.0),
        lambda d: opening(d, "W02").update(id="D02"),
    ],
    ids=["corner", "lintel", "facade_end", "pier", "door_sill", "window_sill", "dup_id"],
)
def test_opening_beyond_limits_rejected(demo_data, mutate):
    mutate(demo_data)
    assert any(p.startswith("building.openings") for p in paths(issues_for(demo_data)))


def test_mm_project_equals_m_project(demo_data):
    m_project = parse_project(json.loads(json.dumps(demo_data)))

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

    to_mm(demo_data)
    mm_project = parse_project(demo_data)
    assert mm_project.building.wall_thickness.original.unit == "mm"
    assert mm_project.building.wall_thickness.unit == "m"

    def lengths(node, out, path=""):
        if isinstance(node, dict):
            if node.get("unit") in LENGTH_UNITS:
                out[path] = node["value"]
            for k, v in node.items():
                if k != "original":  # conversion record keeps the source unit
                    lengths(v, out, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                lengths(v, out, f"{path}[{i}]")
        return out

    a = lengths(m_project.model_dump(mode="json"), {})
    b = lengths(mm_project.model_dump(mode="json"), {})
    assert a.keys() == b.keys() and len(a) > 20
    for key in a:
        assert b[key] == pytest.approx(a[key], abs=1e-9), key


def test_duplicate_camera_rejected(demo_data):
    from exterior_agent.domain.project import CANONICAL_CAMERAS

    cams = [c.model_dump() for c in CANONICAL_CAMERAS]
    cams[9] = dict(cams[0])
    demo_data["cameras"] = cams
    assert "cameras" in paths(issues_for(demo_data))


def test_missing_camera_rejected(demo_data):
    from exterior_agent.domain.project import CANONICAL_CAMERAS

    demo_data["cameras"] = [c.model_dump() for c in CANONICAL_CAMERAS[:9]]
    assert "cameras" in paths(issues_for(demo_data))


def test_load_project_reads_bom(demo_data, tmp_path):
    path = tmp_path / "project.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(demo_data).encode("utf-8"))
    assert load_project(path).project_id == "demo-townhouse"


def test_load_project_bad_json(tmp_path):
    path = tmp_path / "project.json"
    path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ProjectValidationError) as exc:
        load_project(path)
    assert exc.value.issues[0].path == "$"

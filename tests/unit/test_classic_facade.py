"""Neoclassical facade: mouldings, columns, balconies and ornaments as named, sound components."""

import pytest

from exterior_agent.domain.validate import parse_project
from exterior_agent.geometry.classic_facade import classic_facade_objects
from exterior_agent.geometry.classic_massing import (
    classic_massing_objects,
    on_bay_wall,
    opening_frame,
    outline,
)

FIXTURE_NAMES = (
    {"Cornice_F1", "Cornice_F2", "Cornice_F3", "Dentils_Roof", "Cornice_Rake_Front"}
    | {"Pilaster_L", "Pilaster_R"}
    | {"Archivolt_D1", "Keystone_D1", "Door_D1", "Door_D1_Fanlight_Glass", "Door_D1_Fanlight_Frame"}
    | {"Archivolt_D3", "Keystone_D3", "Door_D3_Frame", "Door_D3_Glass"}
    | {"Window_W2_Frame", "Window_W2_Glass", "Hood_W2", "Balcony_W2_Slab", "Balcony_W2_Balusters"}
    | {"Window_W5_Frame", "Window_W5_Glass", "Hood_W5", "Balcony_W5_Slab", "Balcony_W5_Iron"}
    | {"Window_W6_Frame", "Window_W6_Glass", "Archivolt_W6", "Keystone_W6"}
    | {"Balcony_W6_Slab", "Balcony_W6_Iron"}
    | {"Door_D2_Frame", "Door_D2_Glass"}
    | {f"Window_W{k}_{part}" for k in (1, 3, 4, 7, 8) for part in ("Frame", "Glass")}
    | {
        "Bay_Columns",
        "Bay_Pediment",
        "Bay_Pediment_Ornament",
        "Balcony_Bay_Slab",
        "Balcony_Bay_Iron",
    }
    | {"Oculus_Front_Frame", "Oculus_Front_Glass", "Gable_Front_Ornament"}
)
ORNAMENT_PREFIXES = ("Archivolt_", "Keystone_", "Hood_", "Cornice_", "Dentils_", "Pilaster_",
                     "Gable_Front_Ornament", "Bay_Pediment_Ornament")  # fmt: skip


def facade(data):
    return {o.name: o for o in classic_facade_objects(parse_project(data))}


def test_component_names(classic_data):
    assert set(facade(classic_data)) == FIXTURE_NAMES


def test_all_inside_lot(classic_data):
    p = parse_project(classic_data)
    half, depth = p.site.width.value / 2, p.site.depth.value
    for name, o in facade(classic_data).items():
        lo, hi = o.mesh.bounds()
        assert -half - 1e-9 <= lo[0] and hi[0] <= half + 1e-9, name
        assert lo[1] >= -1e-9 and hi[1] <= depth + 1e-9 and lo[2] >= -1e-9, name


def test_ornaments_touch_wall(classic_data):
    p = parse_project(classic_data)
    yf = p.site.front_setback.value
    yb = yf - p.classic.bay.projection.value
    for name, o in facade(classic_data).items():
        if name.startswith(ORNAMENT_PREFIXES):
            host = yb if name.startswith("Bay_Pediment") else yf
            _, hi = o.mesh.bounds()
            assert hi[1] >= host - 0.01, name


def _inside(pt, poly) -> bool:
    x, y, hit = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def test_openings_unobstructed(classic_data):
    """Nothing but an opening's own frame/glass/door sits inside its hole through the wall."""
    p = parse_project(classic_data)
    m, t = p.classic, p.classic.wall_thickness.value
    objects = facade(classic_data)
    for n, f in enumerate(m.floors, start=1):
        for side in ("front", "rear"):
            for o in getattr(f, f"openings_{side}"):
                frame = opening_frame(p, n, side, o)
                hole = outline(o, o.offset.value - frame.u_shift)
                for name, obj in objects.items():
                    if f"_{o.id}" in name:
                        continue
                    for v in obj.mesh.vertices:
                        d = [v[k] - frame.origin[k] for k in range(3)]
                        u = sum(d[k] * frame.u_axis[k] for k in range(3))
                        w = sum(d[k] * frame.v_axis[k] for k in range(3))
                        if 1e-6 < w < t - 1e-6 and _inside((u, d[2]), hole):
                            pytest.fail(f"{name} intrudes into opening {o.id}")
    assert on_bay_wall(m, 2, m.floors[1].openings_front[0]) is False  # D3 is on the loggia facade


def test_deterministic(classic_data):
    assert facade(classic_data) == facade(classic_data)


def test_triangle_budget(classic_data):
    p = parse_project(classic_data)
    total = sum(len(f) - 2 for o in classic_facade_objects(p) + classic_massing_objects(p)
                if o.mesh is not None for f in o.mesh.faces)  # fmt: skip
    assert total <= 400_000


def test_meshes_closed(classic_data):
    for name, o in facade(classic_data).items():
        assert o.mesh.is_closed(), name


def test_toggles(classic_data):
    c = classic_data["classic"]
    c["cornices"]["dentils"]["value"] = False
    c["bay"]["pediment"] = None
    c["bay"]["columns"]["value"] = False
    c["roof"]["gable_front"]["ornament"]["value"] = False
    names = set(facade(classic_data))
    assert "Dentils_Roof" not in names and "Bay_Columns" not in names
    assert not {n for n in names if n.startswith("Bay_Pediment")}
    assert "Gable_Front_Ornament" not in names

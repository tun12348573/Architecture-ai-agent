import itertools

import pytest

from exterior_agent.domain.validate import TOL
from exterior_agent.geometry.layout import WallFrame
from exterior_agent.geometry.mesh import box_mesh
from exterior_agent.geometry.primitives import (
    box_uvs,
    framed_glazing,
    framed_glazing_boxes,
    glass_rail,
    merge_meshes,
)
from tests.unit.geom_helpers import box_overlap_volume

FRONT = WallFrame((-2.5, 4.5, 0.0), (1, 0, 0), (0, 1, 0), 5.0, 0.0)
DOOR = dict(u0=0.9, u1=4.1, z0=0.0, z1=2.6, v_center=0.1, profile=0.06, depth=0.08)


def test_merge_meshes_offsets_indices():
    a = box_mesh((0, 0, 0), (1, 1, 1))
    b = box_mesh((2, 0, 0), (3, 1, 1))
    merged = merge_meshes([a, b])
    assert len(merged.vertices) == 16 and len(merged.faces) == 12
    assert all(0 <= i < 16 for face in merged.faces for i in face)
    assert merged.bounds() == ((0, 0, 0), (3, 1, 1))


def test_four_leaf_door_with_transom():
    members, panes = framed_glazing_boxes(FRONT, columns=4, transom_height=0.5, **DOOR)
    assert len(panes) == 5
    lo = tuple(min(b[0][i] for b in members) for i in range(3))
    hi = tuple(max(b[1][i] for b in members) for i in range(3))
    assert (lo[0], lo[2], hi[0], hi[2]) == pytest.approx((-1.6, 0.0, 1.6, 2.6), abs=TOL)
    for pane in panes:
        assert -1.6 - TOL <= pane[0][0] and pane[1][0] <= 1.6 + TOL
        assert pane[1][1] - pane[0][1] == pytest.approx(0.01)
        for member in members:
            assert box_overlap_volume(pane, member) == pytest.approx(0.0, abs=1e-12)
    for a, b in itertools.combinations(members, 2):
        assert box_overlap_volume(a, b) == pytest.approx(0.0, abs=1e-12)


def test_single_pane_window():
    members, panes = framed_glazing_boxes(FRONT, columns=1, transom_height=0.0, **DOOR)
    assert len(panes) == 1 and len(members) == 4


def test_framed_glazing_meshes_are_closed_boxes():
    frame, glass = framed_glazing(FRONT, columns=4, transom_height=0.5, **DOOR)
    assert len(frame.faces) % 6 == 0 and len(glass.faces) == 5 * 6
    assert frame.is_closed() and glass.is_closed()


def test_glass_rail_is_box():
    rail = glass_rail((-2.0, 3.5, 3.6), (2.0, 3.512, 4.7))
    assert rail.bounds() == ((-2.0, 3.5, 3.6), (2.0, 3.512, 4.7))


def test_box_uvs_are_metric_per_face():
    mesh = box_mesh((0, 0, 0), (2, 3, 4))
    uvs = box_uvs(mesh)
    assert len(uvs) == len(mesh.faces)
    for face, face_uv in zip(mesh.faces, uvs, strict=True):
        assert len(face_uv) == len(face)
        verts = [mesh.vertices[i] for i in face]
        span = [max(v[k] for v in verts) - min(v[k] for v in verts) for k in range(3)]
        us, vs = zip(*face_uv, strict=True)
        extent = (round(max(us) - min(us), 9), round(max(vs) - min(vs), 9))
        if span[2] == 0:  # horizontal face: (x, y)
            assert extent == (2, 3)
        elif span[0] == 0:  # +/-X face: (y, z)
            assert extent == (3, 4)
        else:  # +/-Y face: (x, z)
            assert extent == (2, 4)

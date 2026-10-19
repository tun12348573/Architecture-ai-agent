"""Reusable building blocks: merged meshes, framed glazing, rails and metric box UVs."""

from exterior_agent.geometry.layout import WallFrame
from exterior_agent.geometry.mesh import Bounds, Mesh, Vec3, box_mesh

GLASS_THICKNESS = 0.01


def merge_meshes(meshes: list[Mesh]) -> Mesh:
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    for mesh in meshes:
        offset = len(vertices)
        vertices.extend(mesh.vertices)
        faces.extend(tuple(i + offset for i in face) for face in mesh.faces)
    return Mesh(vertices, faces)


def local_box(frame: WallFrame, u: tuple, v: tuple, z: tuple) -> Bounds:
    """World AABB of a box given in a wall's local (u, v, z) coordinates."""
    corners = [frame.to_world(a, b, c) for a in u for b in v for c in z]
    xs, ys, zs = zip(*corners, strict=True)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def framed_glazing_boxes(
    frame: WallFrame,
    u0: float,
    u1: float,
    z0: float,
    z1: float,
    v_center: float,
    columns: int,
    transom_height: float,
    profile: float,
    depth: float,
) -> tuple[list[Bounds], list[Bounds]]:
    """Frame members and glass panes filling the opening [u0,u1] x [z0,z1].

    Members: two stiles, head, bottom rail, `columns - 1` mullions and a transom bar when
    `transom_height > 0` (measured down from the top). Members and panes only touch.
    """
    p = profile
    vf = (v_center - depth / 2, v_center + depth / 2)
    vg = (v_center - GLASS_THICKNESS / 2, v_center + GLASS_THICKNESS / 2)
    inner_u0, inner_u1 = u0 + p, u1 - p
    members = [
        local_box(frame, (u0, inner_u0), vf, (z0, z1)),
        local_box(frame, (inner_u1, u1), vf, (z0, z1)),
        local_box(frame, (inner_u0, inner_u1), vf, (z1 - p, z1)),
        local_box(frame, (inner_u0, inner_u1), vf, (z0, z0 + p)),
    ]
    panes: list[Bounds] = []
    low_top = z1 - p
    if transom_height > 0:
        zt = z1 - transom_height
        members.append(local_box(frame, (inner_u0, inner_u1), vf, (zt - p / 2, zt + p / 2)))
        panes.append(local_box(frame, (inner_u0, inner_u1), vg, (zt + p / 2, z1 - p)))
        low_top = zt - p / 2
    cell = ((inner_u1 - inner_u0) - (columns - 1) * p) / columns
    for k in range(columns):
        a = inner_u0 + k * (cell + p)
        panes.append(local_box(frame, (a, a + cell), vg, (z0 + p, low_top)))
        if k < columns - 1:
            members.append(local_box(frame, (a + cell, a + cell + p), vf, (z0 + p, low_top)))
    return members, panes


def framed_glazing(frame: WallFrame, **kwargs) -> tuple[Mesh, Mesh]:
    members, panes = framed_glazing_boxes(frame, **kwargs)
    return (
        merge_meshes([box_mesh(*b) for b in members]),
        merge_meshes([box_mesh(*b) for b in panes]),
    )


def glass_rail(lo: Vec3, hi: Vec3) -> Mesh:
    return box_mesh(lo, hi)


def box_uvs(mesh: Mesh) -> list[list[tuple[float, float]]]:
    """Per-face, per-corner UVs in metres, projected on the plane of the dominant normal axis."""
    out = []
    for face in mesh.faces:
        pts = [mesh.vertices[i] for i in face]
        # Newell's method: robust normal for planar polygons.
        n = [0.0, 0.0, 0.0]
        for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        axis = max(range(3), key=lambda k: abs(n[k]))
        keep = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
        out.append([(v[keep[0]], v[keep[1]]) for v in pts])
    return out

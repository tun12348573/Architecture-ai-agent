"""Walls with real rectangular openings, door/window panels, roof slab and site."""

from exterior_agent.domain.project import Project
from exterior_agent.geometry.layout import WallFrame, footprint_bounds, wall_frames
from exterior_agent.geometry.mesh import Bounds, Mesh, MeshBuilder, box_mesh, quad_mesh

Hole = tuple[float, float, float, float]  # (u0, u1, z0, z1)
DOOR_THICKNESS = 0.05
GLASS_THICKNESS = 0.01
CONTEXT_MIN_SIZE = 60.0
CONTEXT_Z = -0.01
WALL_NAMES = {
    "front": "Wall_Front",
    "rear": "Wall_Rear",
    "left": "Wall_Left",
    "right": "Wall_Right",
}


def wall_mesh(length: float, height: float, thickness: float, holes: list[Hole]) -> Mesh:
    """Closed wall solid in local (u, v, z) coordinates with holes cut through v.

    The facade is split into a grid at every hole edge; cells inside a hole are empty.
    Faces are emitted for solid cells on both facade planes and on every solid-cell edge
    that borders an empty cell or the wall boundary, so all vertices are shared.
    """
    us = sorted({0.0, length, *(h[0] for h in holes), *(h[1] for h in holes)})
    zs = sorted({0.0, height, *(h[2] for h in holes), *(h[3] for h in holes)})

    def solid(i: int, k: int) -> bool:
        if not (0 <= i < len(us) - 1 and 0 <= k < len(zs) - 1):
            return False
        um, zm = (us[i] + us[i + 1]) / 2, (zs[k] + zs[k + 1]) / 2
        return not any(u0 < um < u1 and z0 < zm < z1 for u0, u1, z0, z1 in holes)

    t = thickness
    mb = MeshBuilder()
    for i in range(len(us) - 1):
        for k in range(len(zs) - 1):
            if not solid(i, k):
                continue
            ua, ub, za, zb = us[i], us[i + 1], zs[k], zs[k + 1]
            mb.quad([(ua, 0, za), (ub, 0, za), (ub, 0, zb), (ua, 0, zb)], (0, -1, 0))
            mb.quad([(ua, t, za), (ub, t, za), (ub, t, zb), (ua, t, zb)], (0, 1, 0))
            if not solid(i - 1, k):
                mb.quad([(ua, 0, za), (ua, t, za), (ua, t, zb), (ua, 0, zb)], (-1, 0, 0))
            if not solid(i + 1, k):
                mb.quad([(ub, 0, za), (ub, t, za), (ub, t, zb), (ub, 0, zb)], (1, 0, 0))
            if not solid(i, k - 1):
                mb.quad([(ua, 0, za), (ub, 0, za), (ub, t, za), (ua, t, za)], (0, 0, -1))
            if not solid(i, k + 1):
                mb.quad([(ua, 0, zb), (ub, 0, zb), (ub, t, zb), (ua, t, zb)], (0, 0, 1))
    return mb.build()


def _holes(p: Project, wall: str, frame: WallFrame) -> list[tuple[str, Hole]]:
    out = []
    for o in p.building.openings:
        if o.wall == wall:
            u0 = o.offset.value - frame.u_shift
            z0 = o.sill.value
            out.append((o.id, (u0, u0 + o.width.value, z0, z0 + o.height.value)))
    return out


def _local_box(frame: WallFrame, u: tuple, v: tuple, z: tuple) -> Bounds:
    corners = [frame.to_world(a, b, c) for a in u for b in v for c in z]
    xs, ys, zs = zip(*corners, strict=True)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def build_walls(p: Project) -> dict[str, Mesh]:
    h, t = p.building.wall_height.value, p.building.wall_thickness.value
    out = {}
    for wall, frame in wall_frames(p).items():
        local = wall_mesh(frame.length, h, t, [hole for _, hole in _holes(p, wall, frame)])
        out[WALL_NAMES[wall]] = Mesh([frame.to_world(*v) for v in local.vertices], local.faces)
    return out


def opening_boxes(p: Project) -> dict[str, Bounds]:
    t = p.building.wall_thickness.value
    out = {}
    for wall, frame in wall_frames(p).items():
        for opening_id, (u0, u1, z0, z1) in _holes(p, wall, frame):
            out[opening_id] = _local_box(frame, (u0, u1), (0.0, t), (z0, z1))
    return out


def door_window_meshes(p: Project) -> dict[str, Mesh]:
    """Door leaf / glass pane filling each opening, centred in the wall thickness."""
    t = p.building.wall_thickness.value
    frames = wall_frames(p)
    out = {}
    for o in p.building.openings:
        frame = frames[o.wall]
        panel = DOOR_THICKNESS if o.kind == "door" else GLASS_THICKNESS
        u0, z0 = o.offset.value - frame.u_shift, o.sill.value
        lo, hi = _local_box(
            frame,
            (u0, u0 + o.width.value),
            ((t - panel) / 2, (t + panel) / 2),
            (z0, z0 + o.height.value),
        )
        prefix = "Door" if o.kind == "door" else "Window"
        out[f"{prefix}_{o.id}"] = box_mesh(lo, hi)
    return out


def roof_mesh(p: Project) -> Mesh:
    lo, hi = footprint_bounds(p)
    return box_mesh((lo[0], lo[1], hi[2]), (hi[0], hi[1], hi[2] + p.building.roof.thickness.value))


def site_meshes(p: Project) -> dict[str, Mesh]:
    half_w, depth = p.site.width.value / 2, p.site.depth.value
    size = max(CONTEXT_MIN_SIZE, 3 * max(2 * half_w, depth))
    cy = depth / 2
    return {
        "Site_Land": quad_mesh((-half_w, 0.0, 0.0), (half_w, depth, 0.0)),
        "Site_Context": quad_mesh(
            (-size / 2, cy - size / 2, CONTEXT_Z), (size / 2, cy + size / 2, CONTEXT_Z)
        ),
    }

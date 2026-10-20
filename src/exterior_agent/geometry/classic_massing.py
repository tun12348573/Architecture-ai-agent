"""Neoclassical massing: floors with real arched holes, slabs, the bay/loggia, gable roof.

The roof is two clay-tile plates whose ridge runs front to back at x = 0; their eaves end on
the side walls (x = ±W/2) so rain never drains onto a neighbour's lot. Gables close the roof on
the front (with the oculus) and the rear.
"""

import math

from exterior_agent.domain.classic_rules import OCULUS_HEIGHT, bay_range, gable_height
from exterior_agent.geometry.classic_primitives import oriented
from exterior_agent.geometry.layout import WallFrame
from exterior_agent.geometry.mesh import Mesh, box_mesh
from exterior_agent.geometry.modern_interior import backdrop_objects
from exterior_agent.geometry.modern_massing import (
    PlanObject,
    clear_height,
    floor_base_z,
    floor_frames,
    floor_front_y,
)
from exterior_agent.geometry.polygon_wall import (
    arch_outline,
    circle_outline,
    prism_with_holes,
    rect_outline,
)
from exterior_agent.geometry.primitives import local_box, merge_meshes
from exterior_agent.geometry.walls import wall_mesh

GUTTER_WIDTH, GUTTER_HEIGHT = 0.12, 0.1


def outline(o, u0: float) -> list[tuple[float, float]]:
    """Hole outline of an opening in a wall's local (u, z), u0 = its left edge."""
    z0, z1 = o.sill.value, o.sill.value + o.height.value
    u1 = u0 + o.width.value
    return arch_outline(u0, u1, z0, z1) if o.head == "arch" else rect_outline(u0, u1, z0, z1)


def in_bay(m, o) -> bool:
    if m.bay is None:
        return False
    x0, x1 = bay_range(m)
    return o.offset.value >= x0 - 1e-9 and o.offset.value + o.width.value <= x1 + 1e-9


def on_bay_wall(m, n: int, o) -> bool:
    """Openings inside the bay range of an enclosed bay floor sit on the bay's front wall."""
    b = m.bay
    return b is not None and b.from_floor.value < n <= b.to_floor.value and in_bay(m, o)


def bay_world(p) -> tuple[float, float, float, float]:
    """(x0, x1, y_front, y_facade) of the bay."""
    m = p.classic
    x0, x1 = bay_range(m)
    w2, yf = m.footprint_width.value / 2, p.site.front_setback.value
    return -w2 + x0, -w2 + x1, yf - m.bay.projection.value, yf


def _wall(p, n: int, side: str, frame: WallFrame, openings, t: float, h: float, out: list):
    holes = []
    for o in openings:
        u0 = o.offset.value - frame.u_shift
        holes.append(outline(o, u0))
        z0, z1 = o.sill.value, o.sill.value + o.height.value
        box = local_box(frame, (u0, u0 + o.width.value), (0.0, t), (z0, z1))
        out.append(PlanObject(f"Opening_{o.id}", "Openings", None, None, box))
    return prism_with_holes(rect_outline(0.0, frame.length, 0.0, h), holes, t, frame)


def opening_frame(p, n: int, side: str, o) -> WallFrame:
    """Wall frame an opening is cut into: the main facade, the rear, or the bay's front wall."""
    if side == "front" and on_bay_wall(p.classic, n, o):
        x0, x1, yb, _ = bay_world(p)
        return WallFrame((x0, yb, floor_base_z(p.classic, n)), (1, 0, 0), (0, 1, 0), x1 - x0,
                         bay_range(p.classic)[0])  # fmt: skip
    return floor_frames(p, n)[side]


def _floor_objects(p, n: int) -> list[PlanObject]:
    m = p.classic
    f = m.floors[n - 1]
    t, h = m.wall_thickness.value, clear_height(m, n)
    out: list[PlanObject] = []
    for side, frame in floor_frames(p, n).items():
        if side in ("front", "rear"):
            openings = getattr(f, f"openings_{side}")
            if side == "front":
                openings = [o for o in openings if not on_bay_wall(m, n, o)]
            mesh = _wall(p, n, side, frame, openings, t, h, out)
        else:
            local = wall_mesh(frame.length, h, t, [])
            mesh = Mesh([frame.to_world(*v) for v in local.vertices], local.faces)
        out.append(PlanObject(f"Floor{n}_Wall_{side.capitalize()}", "Building", mesh, "MAT_Wall"))
    w2 = m.footprint_width.value / 2
    yr = p.site.front_setback.value + m.footprint_depth.value
    top = floor_base_z(m, n) + f.height.value
    slab = box_mesh((-w2, floor_front_y(p, n), top - m.slab_thickness.value), (w2, yr, top))
    out.append(PlanObject(f"Floor{n}_Slab", "Building", slab, "MAT_Trim"))
    return out


def _bay_objects(p) -> list[PlanObject]:
    m = p.classic
    b = m.bay
    if b is None:
        return []
    x0, x1, yb, yf = bay_world(p)
    t, slab = m.wall_thickness.value, m.slab_thickness.value
    out: list[PlanObject] = []
    for n in range(b.from_floor.value, b.to_floor.value + 1):
        z = floor_base_z(m, n)
        out.append(PlanObject(f"Bay_Slab_F{n}", "Bay", box_mesh((x0, yb, z - slab), (x1, yf, z)),
                              "MAT_Trim"))  # fmt: skip
        if n == b.from_floor.value:
            continue  # the loggia: open front, columns stand on the slab edge
        h = clear_height(m, n)
        bx0, _ = bay_range(m)
        frame = WallFrame((x0, yb, z), (1, 0, 0), (0, 1, 0), x1 - x0, bx0)
        openings = [o for o in m.floors[n - 1].openings_front if on_bay_wall(m, n, o)]
        front = _wall(p, n, "bay", frame, openings, t, h, out)
        sides = [box_mesh((x0, yb + t, z), (x0 + t, yf, z + h)),
                 box_mesh((x1 - t, yb + t, z), (x1, yf, z + h))]  # fmt: skip
        out.append(PlanObject(f"Bay_Wall_F{n}", "Bay", merge_meshes([front, *sides]), "MAT_Wall"))
    top = floor_base_z(m, b.to_floor.value) + m.floors[b.to_floor.value - 1].height.value
    out.append(
        PlanObject("Bay_Roof", "Bay", box_mesh((x0, yb, top - slab), (x1, yf, top)), "MAT_Trim")
    )
    return out


def prism_xz(pts: list[tuple[float, float]], y0: float, y1: float) -> Mesh:
    """Extrude an (x, z) polygon along +Y."""
    n = len(pts)
    verts = [(x, y0, z) for x, z in pts] + [(x, y1, z) for x, z in pts]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)]
    return oriented(verts, faces)


def _roof_objects(p) -> list[PlanObject]:
    m = p.classic
    r = m.roof
    w2, w = m.footprint_width.value / 2, m.footprint_width.value
    yf = p.site.front_setback.value
    yr = yf + m.footprint_depth.value
    top = sum(f.height.value for f in m.floors)
    h = gable_height(m)
    th = r.thickness.value / math.cos(math.radians(r.pitch_deg.value))  # vertical plate depth
    y0, y1 = yf - r.overhang.value, yr + r.overhang.value
    out = []
    for name, sx in (("L", -1), ("R", 1)):
        pts = [(sx * w2, top), (0.0, top + h), (0.0, top + h + th), (sx * w2, top + th)]
        plate = prism_xz(pts, y0, y1)
        cos_p = math.cos(math.radians(r.pitch_deg.value))
        # tile rows run along the ridge: u = y, v = metres up the slope from the eave
        uvs = [
            [(plate.vertices[i][1], abs(plate.vertices[i][0] - sx * w2) / cos_p) for i in f]
            for f in plate.faces
        ]
        out.append(PlanObject(f"Roof_Tiles_{name}", "Roof", plate, "MAT_Roof_Tiles", uvs=uvs))
        if r.gutters.value:
            xa, xb = sorted((sx * w2, sx * (w2 - GUTTER_WIDTH)))
            gutter = box_mesh((xa, y0, top), (xb, y1, top + GUTTER_HEIGHT))
            out.append(PlanObject(f"Gutter_{name}", "Roof", gutter, "MAT_Trim"))
    t = m.wall_thickness.value
    tri = [(0.0, 0.0), (w, 0.0), (w2, h)]
    oculus = circle_outline(w2, OCULUS_HEIGHT * h, r.gable_front.oculus_radius.value)
    front = WallFrame((-w2, yf, top), (1, 0, 0), (0, 1, 0), w, 0.0)
    rear = WallFrame((w2, yr, top), (-1, 0, 0), (0, -1, 0), w, 0.0)
    out.append(
        PlanObject("Gable_Front", "Roof", prism_with_holes(tri, [oculus], t, front), "MAT_Panel")
    )
    out.append(PlanObject("Gable_Rear", "Roof", prism_with_holes(tri, [], t, rear), "MAT_Panel"))
    return out


def classic_massing_objects(p) -> list[PlanObject]:
    out: list[PlanObject] = []
    for n in range(1, len(p.classic.floors) + 1):
        out += _floor_objects(p, n)
    return out + _bay_objects(p) + _roof_objects(p) + backdrop_objects(p)

"""Neoclassical facade: mouldings, pilasters, opening surrounds, doors/windows, balconies, bay
columns and pediment, gable ornament. One named object per component, every mesh closed.

Proportions follow the M2d spike the owner approved (minimum detail level). Front = -Y: wall
faces lie at y = front setback (main facade) or at the bay front; ornaments project to -Y.
"""

import math

from exterior_agent.domain.classic_rules import OCULUS_HEIGHT, column_inset, gable_height
from exterior_agent.geometry.classic_massing import (
    bay_world,
    opening_frame,
    outline,
    prism_xz,
)
from exterior_agent.geometry.classic_primitives import lathe, leaf, spiral, sweep, tube
from exterior_agent.geometry.layout import WallFrame
from exterior_agent.geometry.mesh import Mesh, box_mesh
from exterior_agent.geometry.modern_massing import PlanObject, clear_height, floor_base_z
from exterior_agent.geometry.polygon_wall import (
    arch_outline,
    circle_outline,
    prism_with_holes,
    rect_outline,
)
from exterior_agent.geometry.primitives import local_box, merge_meshes

TAU = 2 * math.pi
PROFILE = 0.06  # window/door frame member width
FRAME_DEPTH = 0.08
BAR = 0.025  # glazing bar half width
CORNICE = [
    (0, 0),
    (0.04, 0),
    (0.04, 0.05),
    (0.08, 0.07),
    (0.1, 0.12),
    (0.16, 0.15),
    (0.24, 0.17),
    (0.24, 0.24),
    (0.28, 0.26),
    (0.28, 0.32),
    (0, 0.32),
]
STRING = [(0, 0), (0.05, 0), (0.07, 0.03), (0.07, 0.09), (0.1, 0.11), (0.1, 0.16), (0, 0.16)]
HOOD = [(0, 0), (0.04, 0), (0.06, 0.03), (0.06, 0.07), (0.09, 0.09), (0.09, 0.12), (0, 0.12)]
ARCHIVOLT = [
    (0, 0),
    (0.05, 0),
    (0.05, 0.04),
    (0.08, 0.06),
    (0.08, 0.13),
    (0.05, 0.15),
    (0.05, 0.2),
    (0, 0.2),
]
RAKE = [(0, 0), (0.12, 0), (0.12, -0.06), (0.08, -0.1), (0.08, -0.2), (0, -0.2)]
RING = [(0, 0), (0.03, 0), (0.05, 0.03), (0.05, 0.08), (0.03, 0.11), (0, 0.12)]
BALUSTER = [
    (0.0, 0.0),
    (0.06, 0.0),
    (0.06, 0.05),
    (0.04, 0.07),
    (0.035, 0.1),
    (0.05, 0.18),
    (0.075, 0.3),
    (0.07, 0.38),
    (0.045, 0.45),
    (0.025, 0.52),
    (0.03, 0.55),
    (0.055, 0.58),
    (0.055, 0.64),
    (0.0, 0.64),
]
SHAFT = [(0.0, 0.0), (0.22, 0.0), (0.22, 0.06), (0.21, 0.08), (0.21, 0.12), (0.2, 0.14)]
SHAFT += [(0.2 - 0.03 * (t / 10) ** 2, 0.14 + 2.57 * t / 10) for t in range(1, 11)]  # entasis
SHAFT += [(0.19, 2.73), (0.0, 2.73)]
SHAFT_H = 2.73
BELL = [(0.0, 0.0), (0.17, 0.0), (0.18, 0.05), (0.2, 0.2), (0.24, 0.36), (0.28, 0.42), (0.0, 0.42)]
BELL_H, ABACUS_H, PLINTH_H = 0.42, 0.08, 0.25
LEAF_ROWS = ((12, 0.17, 0.175), (12, 0.26, 0.185), (8, 0.36, 0.2))  # count, length, radius
IRON_R, IRON_SIDES = 0.011, 6
FACADE, OPENINGS, BALCONIES, BAY = "Facade", "Windows", "Balconies", "Bay"


def _scaled(profile, sd: float, sh: float):
    return [(d * sd, h * sh) for d, h in profile]


def _shift(frame: WallFrame, v: float) -> WallFrame:
    return WallFrame(
        frame.to_world(0.0, v, 0.0), frame.u_axis, frame.v_axis, frame.length, frame.u_shift
    )


def _lbox(frame: WallFrame, u, v, z) -> Mesh:
    return box_mesh(*local_box(frame, u, v, z))


def _squash_y(mesh: Mesh, cy: float, f: float) -> Mesh:
    return Mesh([(x, cy + (y - cy) * f, z) for x, y, z in mesh.vertices], mesh.faces)


def _floor_top(m, n: int) -> float:
    return floor_base_z(m, n) + m.floors[n - 1].height.value


def _ornament_limit(m, n: int) -> float:
    """Highest z an opening surround may reach on floor n (below the next cornice/dentils)."""
    top = _floor_top(m, n) - m.slab_thickness.value
    return top - (0.12 if n == len(m.floors) else 0.0)


# ------------------------------------------------------------------ doors and windows
def _glazing(frame: WallFrame, o, u0: float, t: float) -> tuple[Mesh, Mesh]:
    """Dark frame ring + glazing bars, and the glass plate, both inside the wall."""
    w, z0, z1 = o.width.value, o.sill.value, o.sill.value + o.height.value
    u1 = u0 + w
    inner_u0, inner_u1, inner_z0, inner_z1 = u0 + PROFILE, u1 - PROFILE, z0 + PROFILE, z1 - PROFILE
    if o.head == "arch":
        inner = arch_outline(inner_u0, inner_u1, inner_z0, inner_z1)
        spring = z1 - w / 2
    else:
        inner = rect_outline(inner_u0, inner_u1, inner_z0, inner_z1)
        spring = inner_z1
    ff = _shift(frame, t / 2 - FRAME_DEPTH / 2)
    parts = [prism_with_holes(outline(o, u0), [inner], FRAME_DEPTH, ff)]
    cu = (u0 + u1) / 2
    vb = (t / 2 - FRAME_DEPTH / 2, t / 2 + FRAME_DEPTH / 2)
    parts.append(_lbox(frame, (cu - BAR, cu + BAR), vb, (inner_z0, spring)))  # mullion
    transoms = [spring] if o.head == "arch" else []
    if o.head == "flat" and inner_z1 - inner_z0 > 1.5:
        transoms.append(inner_z0 + (inner_z1 - inner_z0) * 0.62)
    for zt in transoms:
        parts.append(_lbox(frame, (inner_u0, inner_u1), vb, (zt - BAR, zt + BAR)))
    if o.head == "arch":  # fan bars in the arch
        r = w / 2 - PROFILE
        for a in (math.radians(45), math.radians(135)):
            pts = [
                frame.to_world(
                    cu + k * r * math.cos(a) / 4, t / 2, spring + k * r * math.sin(a) / 4
                )
                for k in range(5)
            ]
            parts.append(tube(pts, BAR * 0.8, IRON_SIDES))
    glass = prism_with_holes(inner, [], 0.01, _shift(frame, t / 2 - 0.005))
    return merge_meshes(parts), glass


def _wood_door(frame: WallFrame, o, u0: float, t: float) -> list[tuple[str, Mesh, str]]:
    w, z0, z1 = o.width.value, o.sill.value, o.sill.value + o.height.value
    u1, cu = u0 + w, u0 + w / 2
    zs = z1 - w / 2 if o.head == "arch" else z1
    vl = (t / 2 - 0.03, t / 2 + 0.03)
    parts = [_lbox(frame, (u0, cu), vl, (z0, zs)), _lbox(frame, (cu, u1), vl, (z0, zs))]
    for a, b in ((u0 + 0.12, cu - 0.08), (cu + 0.08, u1 - 0.12)):  # raised panels, street side
        for pz0, pz1 in ((z0 + 0.25, z0 + (zs - z0) * 0.4), (z0 + (zs - z0) * 0.47, zs - 0.15)):
            parts.append(_lbox(frame, (a, b), (t / 2 - 0.05, t / 2 - 0.03), (pz0, pz1)))
    out = [(f"Door_{o.id}", merge_meshes(parts), "MAT_Door_Wood")]
    if o.head == "arch":
        glass = prism_with_holes(
            arch_outline(u0, u1, zs, z1), [], 0.01, _shift(frame, t / 2 - 0.005)
        )
        r = w / 2
        ring = [
            frame.to_world(
                cu + (r - 0.04) * math.cos(math.pi * k / 24),
                t / 2,
                zs + (r - 0.04) * math.sin(math.pi * k / 24),
            )
            for k in range(25)
        ]
        bars = [
            tube(ring, 0.03, 8),
            _lbox(frame, (u0, u1), (t / 2 - 0.04, t / 2 + 0.04), (zs - 0.03, zs + 0.03)),
        ]
        for k in range(1, 6):
            a = math.pi * k / 6
            pts = [
                frame.to_world(
                    cu + j * (r - 0.04) * math.cos(a) / 3,
                    t / 2,
                    zs + 0.03 + j * (r - 0.07) * math.sin(a) / 3,
                )
                for j in range(4)
            ]
            bars.append(tube(pts, 0.015, IRON_SIDES))
        out += [
            (f"Door_{o.id}_Fanlight_Glass", glass, "MAT_Glass"),
            (f"Door_{o.id}_Fanlight_Frame", merge_meshes(bars), "MAT_Frame"),
        ]
    return out


# ------------------------------------------------------------------ iron and balusters
def _iron_belly(
    cx: float, cy: float, rx: float, ry: float, z0: float, z1: float, bulge: float
) -> Mesh:
    """Half-elliptic railing on the street side of (cx, cy) with bellied bars."""
    perimeter = math.pi * (rx + ry) / 2
    n = max(6, round(perimeter / 0.12))
    parts = []
    for k in range(n + 1):
        a = math.pi + math.pi * k / n
        pts = []
        for i in range(13):
            s = i / 12
            b = bulge * math.sin(math.pi * s) ** 1.5
            pts.append(
                (cx + (rx + b) * math.cos(a), cy + (ry + b) * math.sin(a), z0 + (z1 - z0) * s)
            )
        parts.append(tube(pts, IRON_R, IRON_SIDES))
    for z, b, r in (
        (z0 + 0.03, 0.0, 0.018),
        (z1, 0.0, 0.03),
        (z0 + 0.45 * (z1 - z0), bulge * 0.88, 0.012),
    ):
        arc = [
            (
                cx + (rx + b) * math.cos(math.pi + math.pi * i / 48),
                cy + (ry + b) * math.sin(math.pi + math.pi * i / 48),
                z,
            )
            for i in range(49)
        ]
        parts.append(tube(arc, r, IRON_SIDES))
    return merge_meshes(parts)


def _iron_straight(x0: float, x1: float, y: float, z0: float, z1: float) -> Mesh:
    parts = []
    n = max(2, round((x1 - x0) / 0.11))
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        parts.append(tube([(x, y, z0), (x, y, z1)], IRON_R, IRON_SIDES))
    for z, r in ((z0 + 0.02, 0.016), (z1, 0.025)):
        parts.append(tube([(x0, y, z), (x1, y, z)], r, IRON_SIDES))
    zc = z0 + 0.4 * (z1 - z0)
    for k in range(n):  # C-scroll pairs between bars
        xc = x0 + (x1 - x0) * (k + 0.5) / n
        for s in (-1, 1):
            pts = spiral(
                (xc, y, zc + s * 0.05), (s, 0, 0), (0, 0, 1), 0.04, 0.012, 1.1, -math.pi / 2, 24
            )
            parts.append(tube(pts, 0.006, 5))
    return merge_meshes(parts)


def _balustrade(x0: float, x1: float, yc: float, z0: float, rail: float) -> Mesh:
    hb = rail - 0.2
    sh = hb / BALUSTER[-1][1]
    parts = [box_mesh((x0, yc - 0.1, z0), (x1, yc + 0.1, z0 + 0.06))]
    n = max(2, int((x1 - x0 - 0.3) / 0.17))
    for k in range(n):
        x = x0 + 0.2 + (x1 - x0 - 0.4) * k / max(1, n - 1)
        parts.append(lathe([(r, z * sh) for r, z in BALUSTER], (x, yc, z0 + 0.06), 16))
    parts.append(
        box_mesh((x0 - 0.03, yc - 0.12, z0 + 0.06 + hb), (x1 + 0.03, yc + 0.12, z0 + rail))
    )
    for xe in (x0, x1 - 0.18):
        parts.append(box_mesh((xe, yc - 0.11, z0 + 0.06), (xe + 0.18, yc + 0.11, z0 + 0.06 + hb)))
    return merge_meshes(parts)


def _half_slab(cx: float, cy: float, rx: float, ry: float, z: float, corbel: bool) -> Mesh:
    prof = [(0.0, 0.0), (rx, 0.0), (rx, 0.06), (rx + 0.03, 0.09), (rx + 0.03, 0.15), (0.0, 0.15)]
    parts = [_squash_y(lathe(prof, (cx, cy, z - 0.12), 32, math.pi, TAU), cy, ry / (rx + 0.03))]
    if corbel:
        cb = [(0.0, 0.0), (rx * 0.8, 0.0), (rx * 0.55, -0.15), (rx * 0.3, -0.35), (0.0, -0.45)]
        parts.append(
            _squash_y(lathe(cb, (cx, cy, z - 0.12), 24, math.pi, TAU), cy, ry / (rx + 0.03))
        )
    return merge_meshes(parts)


def _balcony(p, n: int, o, frame: WallFrame, u0: float) -> list[PlanObject]:
    m, b = p.classic, o.balcony
    w2 = m.footprint_width.value / 2
    host = frame.origin[1]
    x0 = max(-w2, frame.to_world(u0 - 0.15, 0, 0)[0])
    x1 = min(w2, frame.to_world(u0 + o.width.value + 0.15, 0, 0)[0])
    cx = frame.to_world(u0 + o.width.value / 2, 0, 0)[0]
    zb = floor_base_z(m, n) + (o.sill.value if b.kind == "iron_straight" else 0.0)
    proj, rail = b.projection.value, b.rail_height.value
    out = []
    if b.kind in ("balustrade", "iron_straight"):
        slab = box_mesh((x0, host - proj, zb - 0.12), (x1, host, zb + 0.03))
        out.append(PlanObject(f"Balcony_{o.id}_Slab", BALCONIES, slab, "MAT_Trim"))
        if b.kind == "balustrade":
            rails = _balustrade(x0 + 0.05, x1 - 0.05, host - proj / 2, zb + 0.03, rail)
            out.append(PlanObject(f"Balcony_{o.id}_Balusters", BALCONIES, rails, "MAT_Trim"))
        else:
            top = zb + min(rail, 0.7)
            iron = _iron_straight(x0 + 0.05, x1 - 0.05, host - proj + 0.04, zb + 0.03, top)
            out.append(PlanObject(f"Balcony_{o.id}_Iron", BALCONIES, iron, "MAT_Iron"))
        return out
    room = min(cx + w2, w2 - cx) - 0.05
    rx = min(max(proj, o.width.value / 2 + 0.1), room)
    ry = min(rx if b.kind == "round_iron" else proj, host - 0.3)
    slab = _half_slab(cx, host, rx, ry, zb, corbel=b.kind == "round_iron")
    bulge = 0.04 if b.kind == "round_iron" else 0.1
    iron = _iron_belly(cx, host, rx - 0.06 - bulge, ry - 0.06, zb + 0.03, zb + rail, bulge)
    out.append(PlanObject(f"Balcony_{o.id}_Slab", BALCONIES, slab, "MAT_Trim"))
    out.append(PlanObject(f"Balcony_{o.id}_Iron", BALCONIES, iron, "MAT_Iron"))
    return out


def _opening_objects(p, n: int, side: str, o) -> list[PlanObject]:
    m = p.classic
    frame = opening_frame(p, n, side, o)
    u0 = o.offset.value - frame.u_shift
    t = m.wall_thickness.value
    out: list[PlanObject] = []
    if o.kind == "door_wood":
        out += [
            PlanObject(name, OPENINGS, mesh, mat) for name, mesh, mat in _wood_door(frame, o, u0, t)
        ]
    else:
        prefix = "Door" if o.kind == "door" else "Window"
        ring, glass = _glazing(frame, o, u0, t)
        out += [
            PlanObject(f"{prefix}_{o.id}_Frame", OPENINGS, ring, "MAT_Frame"),
            PlanObject(f"{prefix}_{o.id}_Glass", OPENINGS, glass, "MAT_Glass"),
        ]
    if side != "front":
        return out
    host = frame.origin[1]
    zb = floor_base_z(m, n)
    xl = frame.to_world(u0, 0, 0)[0]
    xr = frame.to_world(u0 + o.width.value, 0, 0)[0]
    z0, z1 = zb + o.sill.value, zb + o.sill.value + o.height.value
    if o.head == "arch":
        r = o.width.value / 2
        zs, cx = z1 - r, (xl + xr) / 2
        path = [(xl, z0), (xl, zs)]
        path += [
            (
                cx + r * math.cos(math.pi - math.pi * k / 32),
                zs + r * math.sin(math.pi - math.pi * k / 32),
            )
            for k in range(1, 32)
        ]
        path += [(xr, zs), (xr, z0)]
        out.append(
            PlanObject(f"Archivolt_{o.id}", FACADE, sweep(path, ARCHIVOLT, host), "MAT_Trim")
        )
    keystone = o.head == "arch" or (o.keystone is not None and o.keystone.value)
    kh = min(0.3, _ornament_limit(m, n) - z1)
    if keystone and kh >= 0.06:
        cx = (xl + xr) / 2
        pts = [
            (cx - 0.11, z1 - 0.02),
            (cx + 0.11, z1 - 0.02),
            (cx + 0.16, z1 + kh),
            (cx - 0.16, z1 + kh),
        ]
        out.append(
            PlanObject(f"Keystone_{o.id}", FACADE, prism_xz(pts, host - 0.12, host), "MAT_Trim")
        )
    if o.hood is not None and o.hood.value and o.head == "flat":
        w2 = m.footprint_width.value / 2
        hood = sweep([(max(-w2, xl - 0.1), z1 + 0.05), (min(w2, xr + 0.1), z1 + 0.05)], HOOD, host)
        out.append(PlanObject(f"Hood_{o.id}", FACADE, hood, "MAT_Trim"))
    if o.balcony is not None:
        out += _balcony(p, n, o, frame, u0)
    return out


# ------------------------------------------------------------------ mouldings and pilasters
def _mouldings(p) -> list[PlanObject]:
    m = p.classic
    w2, yf = m.footprint_width.value / 2, p.site.front_setback.value
    slab, nf = m.slab_thickness.value, len(m.floors)
    c = m.cornices
    out = []
    for n in range(1, nf + 1):
        top = _floor_top(m, n)
        if n < nf:
            mesh = sweep([(-w2, top - 0.16), (w2, top - 0.16)], STRING, yf)
        else:
            prof = _scaled(CORNICE, c.depth.value / 0.28, c.height.value / 0.32)
            mesh = sweep([(-w2, top - slab), (w2, top - slab)], prof, yf)
        out.append(PlanObject(f"Cornice_F{n}", FACADE, mesh, "MAT_Trim"))
    top = _floor_top(m, nf)
    if c.dentils.value:
        teeth, x = [], -w2 + 0.05
        while x + 0.07 <= w2 - 0.05 + 1e-9:
            teeth.append(box_mesh((x, yf - 0.16, top - slab - 0.1), (x + 0.07, yf, top - slab)))
            x += 0.14
        out.append(PlanObject("Dentils_Roof", FACADE, merge_meshes(teeth), "MAT_Trim"))
    h = gable_height(m)
    rake = sweep([(-w2, top), (0.0, top + h), (w2, top)], RAKE, yf)
    out.append(PlanObject("Cornice_Rake_Front", FACADE, rake, "MAT_Trim"))
    return out


def _rosette(cx: float, y: float, cz: float, s: float) -> list[Mesh]:
    parts = [
        box_mesh(
            (cx - 0.025 * s, y - 0.03 * s, cz - 0.025 * s), (cx + 0.025 * s, y, cz + 0.025 * s)
        )
    ]
    for k in range(12):
        a = TAU * k / 12
        parts.append(
            leaf(
                (cx, y, cz),
                (math.cos(a), 0, math.sin(a)),
                (0, -1, 0),
                (-math.sin(a), 0, math.cos(a)),
                0.1 * s,
                0.035 * s,
                0.02 * s,
            )
        )
    return parts


def _pilasters(p) -> list[PlanObject]:
    m = p.classic
    if m.pilasters is None:
        return []
    w2, yf = m.footprint_width.value / 2, p.site.front_setback.value
    pw, pd = m.pilasters.width.value, m.pilasters.depth.value
    top = _floor_top(m, len(m.floors)) - m.slab_thickness.value - 0.12
    out = []
    for name, (x0, x1) in (("L", (-w2, -w2 + pw)), ("R", (w2 - pw, w2))):
        parts = [
            box_mesh((x0, yf - pd, 0.5), (x1, yf, top - 0.2)),
            box_mesh((x0, yf - pd - 0.04, 0.35), (x1, yf, 0.55)),
            box_mesh((x0, yf - pd - 0.05, top - 0.2), (x1, yf, top)),
        ]
        z_ros = floor_base_z(m, min(2, len(m.floors))) + 1.3
        parts += _rosette((x0 + x1) / 2, yf - pd, z_ros, 1.0)
        out.append(PlanObject(f"Pilaster_{name}", FACADE, merge_meshes(parts), "MAT_Trim"))
    return out


# ------------------------------------------------------------------ bay: columns, balcony, pediment
def _column(xc: float, yc: float, z0: float, height: float, r: float) -> list[Mesh]:
    s = r / 0.2
    cap_h = (BELL_H + ABACUS_H) * s
    shaft_h = height - PLINTH_H - cap_h
    half = column_inset(r) - 0.01
    parts = [box_mesh((xc - half, yc - half, z0), (xc + half, yc + half, z0 + PLINTH_H))]
    parts.append(
        lathe([(rr * s, z * shaft_h / SHAFT_H) for rr, z in SHAFT], (xc, yc, z0 + PLINTH_H), 24)
    )
    zc = z0 + PLINTH_H + shaft_h
    parts.append(lathe([(rr * s, z * s) for rr, z in BELL], (xc, yc, zc), 24))
    for row, (count, length, rad) in enumerate(LEAF_ROWS):
        for k in range(count):
            a = TAU * k / count + (math.pi / count if row == 1 else 0.0)
            out = (math.cos(a), math.sin(a), 0.0)
            side = (-math.sin(a), math.cos(a), 0.0)
            origin = (xc + rad * s * out[0], yc + rad * s * out[1], zc + (0.02 + 0.08 * row) * s)
            parts.append(leaf(origin, (0, 0, 1), out, side, length * s, 0.075 * s, 0.045 * s))
    for k in range(4):  # corner volutes under the abacus
        a = math.pi / 4 + k * math.pi / 2
        ox, oy = xc + 0.24 * s * math.cos(a), yc + 0.24 * s * math.sin(a)
        pts = spiral(
            (ox, oy, zc + 0.33 * s),
            (math.cos(a), math.sin(a), 0),
            (0, 0, 1),
            0.065 * s,
            0.013 * s,
            1.3,
            0.0,
            40,
        )
        parts.append(tube(pts, 0.016 * s, IRON_SIDES))
    ah = min(0.3 * s, half)
    parts.append(box_mesh((xc - ah, yc - ah, zc + BELL_H * s), (xc + ah, yc + ah, zc + cap_h)))
    return parts


def _cartouche(cx: float, cz: float, y: float, s: float, ring_r: float) -> list[Mesh]:
    """C-scrolls, scroll leaves and a crowning leaf fan around a ring of radius ring_r."""
    parts = []
    for sd in (-1, 1):
        sx = cx + sd * (ring_r + 0.43 * s)
        pts = spiral(
            (sx, y, cz - 0.25 * s), (sd, 0, 0), (0, 0, 1), 0.22 * s, 0.04 * s, 1.6, math.pi / 2, 60
        )
        parts.append(tube(pts, 0.022 * s, 8))
        tail = [
            (cx + sd * (ring_r + 0.43 * s - 0.35 * s * t), y, cz - 0.03 * s + 0.25 * s * t)
            for t in (i / 12 for i in range(13))
        ]
        parts.append(tube(tail, 0.022 * s, 8))
        for k in range(6):
            a = math.radians(70 + 25 * k) if sd > 0 else math.radians(110 - 25 * k)
            origin = (
                cx + sd * (ring_r + 0.38 * s - 0.07 * s * k),
                y + 0.01,
                cz - 0.32 * s + 0.11 * s * k,
            )
            parts.append(
                leaf(
                    origin,
                    (math.cos(a), 0, math.sin(a)),
                    (0, -1, 0),
                    (-math.sin(a), 0, math.cos(a)),
                    0.22 * s,
                    0.06 * s,
                    0.035 * s,
                )
            )
    for k in range(7):
        a = math.radians(90 + (k - 3) * 22)
        origin = (cx, y + 0.01, cz + ring_r + 0.03 * s)
        parts.append(
            leaf(
                origin,
                (math.cos(a), 0, math.sin(a)),
                (0, -1, 0),
                (-math.sin(a), 0, math.cos(a)),
                (0.32 - 0.04 * abs(k - 3)) * s,
                0.07 * s,
                0.06 * s,
            )
        )
    return parts


def _bay_objects(p) -> list[PlanObject]:
    m = p.classic
    b = m.bay
    if b is None:
        return []
    x0, x1, yb, _ = bay_world(p)
    a, z = b.from_floor.value, b.to_floor.value
    za = floor_base_z(m, a)
    out = []
    if b.columns.value:
        r = b.column_radius.value
        inset = column_inset(r)
        yc = yb + inset
        parts = []
        for xc in (x0 + inset, x1 - inset):
            parts += _column(xc, yc, za, clear_height(m, a), r)
        out.append(PlanObject("Bay_Columns", BAY, merge_meshes(parts), "MAT_Trim"))
    cx, bw = (x0 + x1) / 2, x1 - x0
    rx, ry = bw / 2 - 0.05, min(0.8, yb - 0.3)
    out.append(
        PlanObject("Balcony_Bay_Slab", BALCONIES, _half_slab(cx, yb, rx, ry, za, False), "MAT_Trim")
    )
    iron = _iron_belly(cx, yb, rx - 0.16, ry - 0.06, za + 0.03, za + 1.0, 0.1)
    out.append(PlanObject("Balcony_Bay_Iron", BALCONIES, iron, "MAT_Iron"))
    if b.pediment is not None:
        ph = b.pediment.height.value
        ztop = _floor_top(m, z)
        frame = WallFrame((x0, yb, ztop), (1, 0, 0), (0, 1, 0), bw, 0.0)
        tri = prism_with_holes([(0.0, 0.0), (bw, 0.0), (bw / 2, ph)], [], 0.25, frame)
        rake = sweep([(x0, ztop), (cx, ztop + ph), (x1, ztop)], RAKE, yb)
        base = sweep([(x0, ztop), (x1, ztop)], HOOD, yb)
        out.append(PlanObject("Bay_Pediment", BAY, merge_meshes([tri, rake, base]), "MAT_Trim"))
        if b.pediment.ornament.value:
            s = ph / 2.4
            parts = [
                sweep(
                    [
                        (
                            cx + 0.12 * s * math.cos(-TAU * k / 32),
                            ztop + 0.42 * ph + 0.12 * s * math.sin(-TAU * k / 32),
                        )
                        for k in range(32)
                    ],
                    RING,
                    yb,
                    closed=True,
                )
            ]
            parts += _cartouche(cx, ztop + 0.42 * ph, yb - 0.03, s, 0.12 * s)
            out.append(PlanObject("Bay_Pediment_Ornament", BAY, merge_meshes(parts), "MAT_Trim"))
    return out


# ------------------------------------------------------------------ gable: oculus + ornament
def _gable_objects(p) -> list[PlanObject]:
    m = p.classic
    w2, yf, t = m.footprint_width.value / 2, p.site.front_setback.value, m.wall_thickness.value
    top, h = _floor_top(m, len(m.floors)), gable_height(m)
    r = m.roof.gable_front.oculus_radius.value
    zoc = top + OCULUS_HEIGHT * h
    frame = WallFrame((-w2, yf, top), (1, 0, 0), (0, 1, 0), 2 * w2, 0.0)
    glass = prism_with_holes(
        circle_outline(w2, OCULUS_HEIGHT * h, r), [], 0.01, _shift(frame, t / 2 - 0.005)
    )
    v = (t / 2 - 0.02, t / 2 + 0.02)
    bars = merge_meshes(
        [
            _lbox(frame, (w2 - 0.02, w2 + 0.02), v, (OCULUS_HEIGHT * h - r, OCULUS_HEIGHT * h + r)),
            _lbox(frame, (w2 - r, w2 + r), v, (OCULUS_HEIGHT * h - 0.02, OCULUS_HEIGHT * h + 0.02)),
        ]
    )
    out = [
        PlanObject("Oculus_Front_Frame", FACADE, bars, "MAT_Frame"),
        PlanObject("Oculus_Front_Glass", FACADE, glass, "MAT_Glass"),
    ]
    if m.roof.gable_front.ornament.value:
        ring = sweep(
            [(r * math.cos(-TAU * k / 48), zoc + r * math.sin(-TAU * k / 48)) for k in range(48)],
            RING,
            yf,
            closed=True,
        )
        parts = [ring, *_cartouche(0.0, zoc, yf - 0.04, r / 0.42, r)]
        out.append(PlanObject("Gable_Front_Ornament", FACADE, merge_meshes(parts), "MAT_Trim"))
    return out


def classic_facade_objects(p) -> list[PlanObject]:
    m = p.classic
    out = _mouldings(p) + _pilasters(p)
    for n, f in enumerate(m.floors, start=1):
        for side in ("front", "rear"):
            for o in getattr(f, f"openings_{side}"):
                out += _opening_objects(p, n, side, o)
    return out + _bay_objects(p) + _gable_objects(p)

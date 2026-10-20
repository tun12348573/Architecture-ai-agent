"""Modern facade components: balconies, projecting frames, louvers, canopy, doors, windows."""

from exterior_agent.geometry.mesh import box_mesh
from exterior_agent.geometry.modern_massing import (
    RAIL_THICKNESS,
    PlanObject,
    clear_height,
    floor_base_z,
    floor_frames,
    floor_front_y,
)
from exterior_agent.geometry.primitives import framed_glazing, local_box, merge_meshes

PROFILES = {"door_4leaf": 0.08, "window": 0.06}  # aluminium frame member width per kind
PROFILE_DEPTH = 0.08
LEAF_THICKNESS = 0.05
LOUVER_GAP = 0.05  # clearance between louver blades and the wall face
COLUMNS = {"door_4leaf": 4, "window": 2}


def _balcony(p, i, bal) -> list[PlanObject]:
    m = p.modern
    n = bal.floor.value
    x0 = -m.footprint_width.value / 2 + bal.offset.value
    x1 = x0 + bal.width.value
    yf = floor_front_y(p, n)
    y0 = yf - bal.depth.value
    z = floor_base_z(m, n)
    zt = z + bal.rail_height.value
    slab = box_mesh((x0, y0, z - bal.slab_thickness.value), (x1, yf, z))
    rail = merge_meshes(
        [
            box_mesh((x0, y0, z), (x1, y0 + RAIL_THICKNESS, zt)),
            box_mesh((x0, y0 + RAIL_THICKNESS, z), (x0 + RAIL_THICKNESS, yf, zt)),
            box_mesh((x1 - RAIL_THICKNESS, y0 + RAIL_THICKNESS, z), (x1, yf, zt)),
        ]
    )
    return [
        PlanObject(f"Balcony_F{n}", "Balconies", slab, "MAT_Wall"),
        PlanObject(f"Balcony_F{n}_Rail", "Balconies", rail, "MAT_Glass"),
    ]


def _frame(p, fr) -> PlanObject:
    """Inverted U: two posts and a top beam projecting from the facade."""
    m = p.modern
    a, b = fr.from_floor.value, fr.to_floor.value
    w, th = m.footprint_width.value, fr.thickness.value
    x0, x1 = -w / 2, w / 2
    yf = floor_front_y(p, a)
    y0 = yf - fr.depth.value
    z0 = floor_base_z(m, a)
    z1 = floor_base_z(m, b) + m.floors[b - 1].height.value
    mesh = merge_meshes(
        [
            box_mesh((x0, y0, z0), (x0 + th, yf, z1)),
            box_mesh((x1 - th, y0, z0), (x1, yf, z1)),
            box_mesh((x0 + th, y0, z1 - th), (x1 - th, yf, z1)),
        ]
    )
    return PlanObject(f"Frame_F{a}-{b}", "Facade", mesh, "MAT_Frame")


def _louvers(p, lv) -> list[PlanObject]:
    m = p.modern
    n = lv.floor.value
    count, bw, bd = lv.count.value, lv.blade_width.value, lv.blade_depth.value
    x_start = -m.footprint_width.value / 2 + lv.offset.value
    step = (lv.width.value - bw) / (count - 1)
    yf = floor_front_y(p, n)
    z0 = floor_base_z(m, n)
    z1 = z0 + clear_height(m, n)
    for fr in m.frames:  # stop under the top beam of a frame that ends on this floor
        if fr.to_floor.value == n:
            beam_bottom = z0 + m.floors[n - 1].height.value - fr.thickness.value
            z1 = min(z1, beam_bottom)
    out = []
    for k in range(count):
        x = x_start + k * step
        mesh = box_mesh((x, yf - LOUVER_GAP - bd, z0), (x + bw, yf - LOUVER_GAP, z1))
        out.append(PlanObject(f"Louver_F{n}_{k + 1}", "Facade", mesh, "MAT_Louver"))
    return out


def _canopy(p) -> PlanObject:
    m, c = p.modern, p.modern.canopy
    w = m.footprint_width.value
    yf = floor_front_y(p, 1)
    z = c.height.value
    mesh = box_mesh((-w / 2, yf - c.depth.value, z), (w / 2, yf, z + c.thickness.value))
    return PlanObject("Canopy", "Facade", mesh, "MAT_Wall")


def _openings(p) -> list[PlanObject]:
    m = p.modern
    t = m.wall_thickness.value
    out = []
    for n, f in enumerate(m.floors, start=1):
        frames = floor_frames(p, n)
        for side in ("front", "rear"):
            frame = frames[side]
            for o in getattr(f, f"openings_{side}"):
                u0, z0 = o.offset.value - frame.u_shift, o.sill.value
                u1, z1 = u0 + o.width.value, z0 + o.height.value
                if o.kind == "door":
                    v = (t / 2 - LEAF_THICKNESS / 2, t / 2 + LEAF_THICKNESS / 2)
                    leaf = box_mesh(*local_box(frame, (u0, u1), v, (z0, z1)))
                    out.append(PlanObject(f"Door_{o.id}", "Doors", leaf, "MAT_Door"))
                    continue
                transom = o.transom_height.value if o.transom_height is not None else 0.0
                frame_mesh, glass = framed_glazing(
                    frame,
                    u0=u0,
                    u1=u1,
                    z0=z0,
                    z1=z1,
                    v_center=t / 2,
                    columns=COLUMNS[o.kind],
                    transom_height=transom if o.kind == "door_4leaf" else 0.0,
                    profile=PROFILES[o.kind],
                    depth=PROFILE_DEPTH,
                )
                prefix, collection = (
                    ("Door", "Doors") if o.kind == "door_4leaf" else ("Window", "Windows")
                )
                out.append(
                    PlanObject(f"{prefix}_{o.id}_Frame", collection, frame_mesh, "MAT_Aluminium")
                )
                out.append(PlanObject(f"{prefix}_{o.id}_Glass", collection, glass, "MAT_Glass"))
    return out


def facade_objects(p) -> list[PlanObject]:
    m = p.modern
    out: list[PlanObject] = []
    for i, bal in enumerate(m.balconies):
        out += _balcony(p, i, bal)
    out += [_frame(p, fr) for fr in m.frames]
    for lv in m.louvers:
        out += _louvers(p, lv)
    if m.canopy is not None:
        out.append(_canopy(p))
    out += _openings(p)
    return out

"""Modern townhouse massing: stacked floors with real openings, slabs, terraces and roof."""

from dataclasses import dataclass

from exterior_agent.geometry.layout import WallFrame
from exterior_agent.geometry.mesh import Bounds, Mesh, box_mesh
from exterior_agent.geometry.primitives import glass_rail, local_box, merge_meshes
from exterior_agent.geometry.walls import wall_mesh

TOL = 0.001
RAIL_HEIGHT = 1.1
RAIL_THICKNESS = 0.012
PERGOLA_HEIGHT = 2.6
PERGOLA_POST = 0.12
PERGOLA_SLAT = 0.06
PERGOLA_SLAT_SPACING = 0.4
WALL_NAMES = ("Front", "Rear", "Left", "Right")


@dataclass(frozen=True)
class PlanObject:
    name: str
    collection: str
    mesh: Mesh | None
    material: str | None
    empty_box: Bounds | None = None


def floor_base_z(m, n: int) -> float:
    return sum(f.height.value for f in m.floors[: n - 1])


def floor_front_y(p, n: int) -> float:
    return p.site.front_setback.value + p.modern.floors[n - 1].front_setback.value


def clear_height(m, n: int) -> float:
    return m.floors[n - 1].height.value - m.slab_thickness.value


def floor_frames(p, n: int) -> dict[str, WallFrame]:
    m = p.modern
    t, w = m.wall_thickness.value, m.footprint_width.value
    x0, x1 = -w / 2, w / 2
    yf = floor_front_y(p, n)
    yr = p.site.front_setback.value + m.footprint_depth.value
    z = floor_base_z(m, n)
    depth = yr - yf
    return {
        "front": WallFrame((x0, yf, z), (1, 0, 0), (0, 1, 0), w, 0.0),
        "rear": WallFrame((x1, yr, z), (-1, 0, 0), (0, -1, 0), w, 0.0),
        "left": WallFrame((x0, yr - t, z), (0, -1, 0), (1, 0, 0), depth - 2 * t, t),
        "right": WallFrame((x1, yf + t, z), (0, 1, 0), (-1, 0, 0), depth - 2 * t, t),
    }


def pergola(x0: float, x1: float, y0: float, y1: float, z0: float) -> Mesh:
    """Four posts, two side beams along y and slats along x; parts only touch."""
    p, top = PERGOLA_POST, z0 + PERGOLA_HEIGHT
    parts = [
        box_mesh((x, y, z0), (x + p, y + p, top - p)) for x in (x0, x1 - p) for y in (y0, y1 - p)
    ]
    parts += [box_mesh((x, y0, top - p), (x + p, y1, top)) for x in (x0, x1 - p)]
    y = y0 + p
    while y + PERGOLA_SLAT <= y1 - p + TOL:
        parts.append(box_mesh((x0 + p, y, top - p), (x1 - p, y + PERGOLA_SLAT, top)))
        y += PERGOLA_SLAT_SPACING
    return merge_meshes(parts)


def _floor_objects(p, n: int) -> list[PlanObject]:
    m = p.modern
    f = m.floors[n - 1]
    t, h = m.wall_thickness.value, clear_height(m, n)
    out = []
    for side, frame in floor_frames(p, n).items():
        openings = getattr(f, f"openings_{side}", []) if side in ("front", "rear") else []
        holes = []
        for o in openings:
            u0 = o.offset.value - frame.u_shift
            z0 = o.sill.value
            hole = (u0, u0 + o.width.value, z0, z0 + o.height.value)
            holes.append(hole)
            box = local_box(frame, hole[:2], (0.0, t), hole[2:])
            out.append(PlanObject(f"Opening_{o.id}", "Openings", None, None, box))
        local = wall_mesh(frame.length, h, t, holes)
        mesh = Mesh([frame.to_world(*v) for v in local.vertices], local.faces)
        out.append(PlanObject(f"Floor{n}_Wall_{side.capitalize()}", "Building", mesh, "MAT_Wall"))
    return out


def massing_objects(p) -> list[PlanObject]:
    m = p.modern
    n_floors = len(m.floors)
    w = m.footprint_width.value
    x0, x1 = -w / 2, w / 2
    yr = p.site.front_setback.value + m.footprint_depth.value
    out: list[PlanObject] = []
    for n in range(1, n_floors + 1):
        out += _floor_objects(p, n)
        yf = floor_front_y(p, n)
        top = floor_base_z(m, n) + m.floors[n - 1].height.value
        slab_lo = top - m.slab_thickness.value
        is_roof = n == n_floors
        has_terrace = not is_roof and floor_front_y(p, n + 1) > yf + TOL
        material = "MAT_Roof" if is_roof else ("MAT_Terrace_Floor" if has_terrace else "MAT_Wall")
        slab = box_mesh((x0, yf, slab_lo), (x1, yr, top))
        out.append(PlanObject(f"Floor{n}_Slab", "Building", slab, material))
        if has_terrace:
            rail = glass_rail((x0, yf, top), (x1, yf + RAIL_THICKNESS, top + RAIL_HEIGHT))
            out.append(PlanObject(f"Floor{n}_Terrace_Rail", "Roof", rail, "MAT_Glass"))
            flag = m.floors[n - 1].terrace_pergola
            if flag is not None and flag.value:
                y_back = floor_front_y(p, n + 1)
                mesh = pergola(x0, x1, yf + 0.05, y_back, top)
                out.append(
                    PlanObject(f"Floor{n}_Terrace_Pergola", "Roof", mesh, "MAT_Pergola_Wood")
                )
    out += _roof_objects(p, x0, x1, floor_front_y(p, n_floors), yr, top)
    return out


PLANT_SPACING = 0.8


def roof_plant_positions(p) -> list[tuple[float, float, float]]:
    """Plant base points spread along the top of the roof planter (empty without a garden)."""
    m = p.modern
    g = m.roof.garden
    if g is None:
        return []
    n = len(m.floors)
    pt = m.roof.parapet_thickness.value
    x0 = -m.footprint_width.value / 2 + pt
    inner = m.footprint_width.value - 2 * pt
    y = floor_front_y(p, n) + pt + g.planter_width.value / 2
    z = floor_base_z(m, n) + m.floors[n - 1].height.value + g.planter_height.value
    count = max(1, round(inner / PLANT_SPACING))
    return [(x0 + (i + 0.5) * inner / count, y, z) for i in range(count)]


def _roof_objects(p, x0: float, x1: float, yf: float, yr: float, z: float) -> list[PlanObject]:
    r = p.modern.roof
    pt, ph = r.parapet_thickness.value, r.parapet_height.value
    ring = merge_meshes(
        [
            box_mesh((x0, yf, z), (x1, yf + pt, z + ph)),
            box_mesh((x0, yr - pt, z), (x1, yr, z + ph)),
            box_mesh((x0, yf + pt, z), (x0 + pt, yr - pt, z + ph)),
            box_mesh((x1 - pt, yf + pt, z), (x1, yr - pt, z + ph)),
        ]
    )
    out = [PlanObject("Parapet", "Roof", ring, "MAT_Wall")]
    sh = r.stair_head
    sw, sd = sh.width.value, sh.depth.value
    stair = box_mesh((-sw / 2, yr - pt - sd, z), (sw / 2, yr - pt, z + sh.height.value))
    out.append(PlanObject("StairHead", "Roof", stair, "MAT_Wall"))
    if r.garden is not None:
        g = r.garden
        py0, py1 = yf + pt, yf + pt + g.planter_width.value
        planter = box_mesh((x0 + pt, py0, z), (x1 - pt, py1, z + g.planter_height.value))
        out.append(PlanObject("Planter_Roof_1", "Roof", planter, "MAT_Soil"))
        if g.pergola.value:
            mesh = pergola(x0 + pt, x1 - pt, py1 + 0.3, yr - pt - sd - 0.3, z)
            out.append(PlanObject("Roof_Pergola", "Roof", mesh, "MAT_Pergola_Wood"))
    return out

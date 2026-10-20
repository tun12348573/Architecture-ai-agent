"""Illustrative street context around a modern_townhouse lot (never measured data).

Front = −Y: the lot's front boundary is y = 0, the sidewalk and road lie at y < 0 and the
neighbour townhouses stand beside the lot (|x| > W/2). Everything is in collection
"Context", deterministic for a given seed, and excluded from camera fitting and lot checks.
"""

import random
from dataclasses import dataclass

from exterior_agent.geometry.mesh import Mesh, box_mesh, quad_mesh
from exterior_agent.geometry.modern_massing import PlanObject
from exterior_agent.geometry.primitives import merge_meshes
from exterior_agent.geometry.walls import wall_mesh

KERB_HEIGHT = 0.15
KERB_WIDTH = 0.15
NEIGHBOUR_GAP = 0.02  # no coplanar faces against the main house side walls
NEIGHBOUR_FLOOR_HEIGHT = 3.3
NEIGHBOUR_RECESS = 0.1  # windows sit this far behind the neighbour's facade
STREET_HALF_LENGTH = 60.0
FAR_GROUND_SIZE = 2000.0  # twice the camera clip distance: no ground edge in any view
PARK_DEPTH = 20.0
DASH, DASH_GAP, DASH_WIDTH = 3.0, 3.0, 0.15
NEIGHBOUR_TINTS = (  # multiplied onto materials.neighbour_wall
    (0.97, 0.93, 0.85),
    (0.86, 0.89, 0.92),
    (0.95, 0.85, 0.76),
    (0.88, 0.92, 0.84),
    (0.93, 0.90, 0.88),
)
COLLECTION = "Context"


@dataclass(frozen=True)
class NeighbourSpec:
    name: str
    x0: float
    x1: float
    y0: float
    y1: float
    floors: int
    tint: int


def neighbour_specs(p) -> list[NeighbourSpec]:
    c = p.context
    if c is None or c.neighbours is None:
        return []
    rng = random.Random(c.neighbours.seed.value)
    half, depth = p.site.width.value / 2, p.body.footprint_depth.value
    out = []
    for side, sign in (("L", -1), ("R", 1)):
        edge = half + NEIGHBOUR_GAP  # distance from the centre line to the next free x
        for k in range(1, c.neighbours.per_side.value + 1):
            # whole millimetres: wall_mesh snaps to 1 µm, float noise would leak into the lot
            width = round(rng.uniform(4.0, 6.0), 3)
            y0 = round(rng.uniform(0.0, 3.0), 3)
            y1 = round(y0 + depth + rng.uniform(-2.0, 2.0), 3)
            floors = rng.randint(2, max(2, len(p.body.floors)))  # never tower over the house
            tint = rng.randrange(len(NEIGHBOUR_TINTS))
            inner, outer = sign * edge, sign * round(edge + width, 6)
            x0, x1 = min(inner, outer), max(inner, outer)
            out.append(NeighbourSpec(f"Neighbour_{side}{k}", x0, x1, y0, y1, floors, tint))
            edge = round(edge + width, 6)
    return out


def _neighbour(n: NeighbourSpec) -> tuple[Mesh, Mesh]:
    """Body set back by the recess, a holed facade skin in front, dark panes in the holes."""
    w, h = n.x1 - n.x0, n.floors * NEIGHBOUR_FLOOR_HEIGHT
    body = box_mesh((n.x0, n.y0 + NEIGHBOUR_RECESS, 0.0), (n.x1, n.y1, h))
    margin = min(0.6, w / 5)
    holes = [(margin, w - margin, 0.0, 2.6)]  # ground-floor shopfront
    for f in range(1, n.floors):
        z = f * NEIGHBOUR_FLOOR_HEIGHT
        holes.append((margin, w - margin, z + 0.9, z + NEIGHBOUR_FLOOR_HEIGHT - 0.5))
    skin = wall_mesh(w, h, NEIGHBOUR_RECESS, holes)
    skin = Mesh([(n.x0 + u, n.y0 + v, z) for u, v, z in skin.vertices], skin.faces)
    y = n.y0 + NEIGHBOUR_RECESS - 0.002  # just in front of the body face
    panes = merge_meshes([quad_wall(n.x0 + u0, n.x0 + u1, y, z0, z1) for u0, u1, z0, z1 in holes])
    return merge_meshes([body, skin]), panes


def quad_wall(x0: float, x1: float, y: float, z0: float, z1: float) -> Mesh:
    """Vertical quad in the plane y, facing −Y (towards the street)."""
    return Mesh([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [(0, 1, 2, 3)])


def _dashes(y: float, z: float) -> Mesh:
    parts, x = [], -STREET_HALF_LENGTH
    while x + DASH <= STREET_HALF_LENGTH:
        parts.append(quad_mesh((x, y - DASH_WIDTH / 2, z), (x + DASH, y + DASH_WIDTH / 2, z)))
        x += DASH + DASH_GAP
    return merge_meshes(parts)


def context_objects(p) -> list[PlanObject]:
    c = p.context
    if c is None:
        return []
    L, sw, rw = STREET_HALF_LENGTH, c.sidewalk_width.value, c.road_width.value
    half, kz = p.site.width.value / 2, -KERB_HEIGHT
    road_y0, road_y1 = -sw - rw, -sw
    specs = neighbour_specs(p)
    back = max([p.site.depth.value] + [n.y1 for n in specs]) + STREET_HALF_LENGTH
    depth = p.site.depth.value
    out = [
        PlanObject(
            "Sidewalk_Front", COLLECTION, box_mesh((-L, -sw + KERB_WIDTH, kz), (L, 0.0, 0.0)),
            "MAT_Sidewalk",
        ),
        PlanObject("Kerb_Front", COLLECTION, box_mesh((-L, -sw, kz), (L, -sw + KERB_WIDTH, 0.0)),
                   "MAT_Kerb"),
        PlanObject("Road", COLLECTION, quad_mesh((-L, road_y0, kz), (L, road_y1, kz)),
                   "MAT_Asphalt"),
        # paved ground beside the lot, under the neighbours
        # z = 0 ground closing around the lot (beside, under the neighbours, and behind)
        PlanObject("Ground_Left", COLLECTION, quad_mesh((-L, 0.0, 0.0), (-half, back, 0.0)),
                   "MAT_Sidewalk"),
        PlanObject("Ground_Rear", COLLECTION, quad_mesh((-half, depth, 0.0), (half, back, 0.0)),
                   "MAT_Sidewalk"),
        PlanObject("Ground_Right", COLLECTION, quad_mesh((half, 0.0, 0.0), (L, back, 0.0)),
                   "MAT_Sidewalk"),
    ]  # fmt: skip
    if c.front.value == "road":
        out.append(
            PlanObject("Road_Marking", COLLECTION, _dashes((road_y0 + road_y1) / 2, kz + 0.005),
                       "MAT_Road_Marking")
        )  # fmt: skip
        out.append(
            PlanObject("Sidewalk_Opposite", COLLECTION,
                       box_mesh((-L, road_y0 - sw, kz), (L, road_y0, 0.0)), "MAT_Sidewalk")
        )  # fmt: skip
    else:
        lawn = box_mesh((-L, road_y0 - PARK_DEPTH, kz), (L, road_y0, 0.0))
        out.append(PlanObject("Park_Lawn", COLLECTION, lawn, "MAT_Grass"))
    for n in specs:
        body, panes = _neighbour(n)
        out.append(PlanObject(n.name, COLLECTION, body, f"MAT_Neighbour_{n.tint + 1}"))
        out.append(PlanObject(f"{n.name}_Glass", COLLECTION, panes, "MAT_Neighbour_Glass"))
    return out

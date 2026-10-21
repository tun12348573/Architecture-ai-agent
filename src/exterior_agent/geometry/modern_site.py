"""Modern townhouse site: yards, front fence and gate, placeholder car and motorbikes."""

from exterior_agent.domain.modern_rules import (
    BIKE_GAP,
    BIKE_LENGTH,
    BIKE_WIDTH,
    CAR_LENGTH,
    CAR_WIDTH,
)
from exterior_agent.geometry.classic_primitives import lathe
from exterior_agent.geometry.context import FAR_GROUND_SIZE, KERB_HEIGHT
from exterior_agent.geometry.mesh import Mesh, box_mesh, quad_mesh
from exterior_agent.geometry.modern_massing import PlanObject
from exterior_agent.geometry.primitives import merge_meshes
from exterior_agent.geometry.walls import site_meshes

FENCE_THICKNESS = 0.05
LOT_BASE_Z = -0.005  # just under the yard quads (no coplanar faces)
GATE_BAR = 0.04
GATE_BAR_SPACING = 0.12
BIKE_HEIGHT = 1.1
CAR_HEIGHT = 1.5


def _gate(x0: float, x1: float, height: float):
    """Vertical bars between a bottom and a top rail; parts only touch."""
    y0, y1 = 0.0, FENCE_THICKNESS
    rail = GATE_BAR
    parts = [
        box_mesh((x0, y0, 0.0), (x1, y1, rail)),
        box_mesh((x0, y0, height - rail), (x1, y1, height)),
    ]
    x = x0
    while x + GATE_BAR <= x1 + 1e-9:
        parts.append(box_mesh((x, y0, rail), (x + GATE_BAR, y1, height - rail)))
        x += GATE_BAR_SPACING
    if x - GATE_BAR_SPACING + GATE_BAR < x1 - 1e-9:  # close the far edge
        parts.append(box_mesh((x1 - GATE_BAR, y0, rail), (x1, y1, height - rail)))
    return merge_meshes(parts)


def _car(cx: float, y0: float):
    """Placeholder car (replaced by a CC0 model in M2b when available): body, cabin, wheels."""
    x0, x1 = cx - CAR_WIDTH / 2, cx + CAR_WIDTH / 2
    y1 = y0 + CAR_LENGTH
    wheel = 0.6
    parts = [
        box_mesh((x0, y0, wheel / 2), (x1, y1, 1.0)),
        box_mesh((x0 + 0.1, y0 + 1.1, 1.0), (x1 - 0.1, y1 - 1.3, CAR_HEIGHT)),
    ]
    for wx in (x0, x1 - 0.25):
        for wy in (y0 + 0.5, y1 - 0.5 - wheel):
            parts.append(box_mesh((wx, wy, 0.0), (wx + 0.25, wy + wheel, wheel / 2)))
    return merge_meshes(parts)


def _motorbike(x0: float, y0: float):
    x1, y1 = x0 + BIKE_WIDTH, y0 + BIKE_LENGTH
    xm0, xm1 = x0 + 0.25, x1 - 0.25
    return merge_meshes(
        [
            box_mesh((xm0, y0, 0.0), (xm1, y0 + 0.6, 0.6)),
            box_mesh((xm0, y1 - 0.6, 0.0), (xm1, y1, 0.6)),
            box_mesh((x0, y0 + 0.6, 0.3), (x1, y1 - 0.6, BIKE_HEIGHT)),
        ]
    )


def _context_ground(p) -> Mesh:
    """Far ground; dropped below the road when a street context is drawn on top of it."""
    mesh = site_meshes(p)["Site_Context"]
    if p.context is None:
        return mesh
    half, cy, z = FAR_GROUND_SIZE / 2, p.site.depth.value / 2, -KERB_HEIGHT - 0.01
    return quad_mesh((-half, cy - half, z), (half, cy + half, z))


PIER, PIER_CAP = 0.45, 0.4  # gate pier width and the height it rises above the fence
LANTERN = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.04), (0.06, 0.06), (0.09, 0.3), (0.11, 0.34),
           (0.03, 0.42), (0.0, 0.45)]  # fmt: skip


def _pier(x0: float, x1: float, height: float) -> tuple[Mesh, Mesh]:
    pier = merge_meshes(
        [box_mesh((x0, 0.0, 0.0), (x1, PIER, height - 0.1)),
         box_mesh((x0, 0.0, height - 0.1), (x1, PIER, height))]
    )  # fmt: skip
    lantern = lathe(LANTERN, ((x0 + x1) / 2, PIER / 2, height), 16)
    return pier, lantern


def site_objects(p) -> list[PlanObject]:
    m, s = p.body, p.site
    half = s.width.value / 2
    fs = s.front_setback.value
    yr = fs + m.footprint_depth.value
    yard = m.front_yard
    front_mat = "MAT_Paving" if yard.kind.value == "parking" else "MAT_Grass"
    out = [
        PlanObject("Yard_Front", "Site", quad_mesh((-half, 0.0, 0.0), (half, fs, 0.0)), front_mat),
        PlanObject(
            "Yard_Rear",
            "Site",
            quad_mesh((-half, yr, 0.0), (half, s.depth.value, 0.0)),
            "MAT_Grass",
        ),
        PlanObject("Site_Context", "Site", _context_ground(p), "MAT_Context_Ground"),
    ]
    if p.context is not None:  # the far ground drops below the road: keep a floor under the house
        base = quad_mesh((-half, 0.0, LOT_BASE_Z), (half, s.depth.value, LOT_BASE_Z))
        out.append(PlanObject("Lot_Base", "Site", base, "MAT_Paving"))
    gw, fh = yard.gate_width.value, yard.fence_height.value
    metal = "MAT_Iron" if p.template == "neoclassical_townhouse" else "MAT_Aluminium"
    piers = yard.gate_piers is not None and yard.gate_piers.value and gw / 2 + PIER <= half
    edge = gw / 2 + (PIER if piers else 0.0)  # fences start beside the gate or its piers
    for name, (a, c) in (("Fence_Left", (-half, -edge)), ("Fence_Right", (edge, half))):
        if c - a > 1e-9:
            mesh = box_mesh((a, 0.0, 0.0), (c, FENCE_THICKNESS, fh))
            out.append(PlanObject(name, "Site", mesh, metal))
    out.append(PlanObject("Gate", "Site", _gate(-gw / 2, gw / 2, yard.gate_height.value), metal))
    if piers:
        for side, (a, c) in (("L", (-edge, -gw / 2)), ("R", (gw / 2, edge))):
            pier, lantern = _pier(a, c, fh + PIER_CAP)
            out.append(PlanObject(f"Gate_Pier_{side}", "Site", pier, "MAT_Trim"))
            out.append(PlanObject(f"Gate_Lantern_{side}", "Site", lantern, "MAT_Iron"))

    usable = fs - FENCE_THICKNESS
    if yard.car.value:
        y0 = FENCE_THICKNESS + (usable - CAR_LENGTH) / 2
        out.append(PlanObject("Prop_Car", "Props", _car(0.0, y0), "MAT_Props"))
    # Motorbikes parked near the house: alternating either side of the car, or one centred row.
    n, pitch = yard.motorbikes.value, BIKE_WIDTH + BIKE_GAP
    if yard.car.value:
        lane = CAR_WIDTH / 2 + BIKE_GAP
        slots = [lane + (k // 2) * pitch if k % 2 == 0 else -lane - (k // 2) * pitch - BIKE_WIDTH
                 for k in range(n)]  # fmt: skip
    else:
        start = -(n * pitch - BIKE_GAP) / 2
        slots = [start + k * pitch for k in range(n)]
    by = fs - 0.2 - BIKE_LENGTH
    for k, x in enumerate(slots, start=1):
        out.append(PlanObject(f"Prop_Motorbike_{k}", "Props", _motorbike(x, by), "MAT_Props"))
    return out

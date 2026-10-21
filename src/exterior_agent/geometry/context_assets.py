"""Where the illustrative CC0 models go: pots, street trees, lamps and a garden-yard tree.

Deterministic for a given project (seeded RNG, golden-angle turns). Trees and lamps never
stand in front of the lot, so they cannot hide the facade in the front views.
"""

import random
from dataclasses import dataclass

from exterior_agent.geometry.context import PARK_DEPTH, STREET_HALF_LENGTH
from exterior_agent.geometry.modern_massing import floor_base_z, floor_front_y

PLANT_TURN = 2.399963  # golden angle: varied but deterministic rotations
POT_INSET = 0.35  # from the balcony slab corner at the rail side
TERRACE_POT_SIDE, TERRACE_POT_BACK = 0.5, 0.4
TREE_SPACING, TREE_FIRST, TREE_KERB_OFFSET = 8.0, 4.0, 0.8
LAMP_SPACING, LAMP_FIRST, LAMP_KERB_OFFSET = 20.0, 7.0, 0.4
LOT_CLEARANCE = 1.0  # street trees/lamps keep |x| >= W/2 + this
YARD_TREE_MAX_RADIUS, YARD_TREE_HEIGHT, YARD_WALKWAY = 1.5, 2.6, 1.0  # walkway: |x| < 1 m
YARD_MARGIN = 0.3  # to the fence and the facade
TREE_MAX_RADIUS, TREE_MAX_HEIGHT, TREE_MIN_RADIUS = 4.0, 7.0, 1.0  # island_tree_02 is wide
LOT_MARGIN = 0.3  # street-tree canopies keep this far from the lot side lines
POT_FIT = (0.6, 1.0)
FRONT_VIEWS = ("01_front", "05_front_left", "06_front_right")
CANOPY_BASE = 0.25  # canopy starts at this share of the tree height; a thin trunk below
TRUNK_RADIUS = 0.2
TREE_HEIGHT_RATIO = 1.2  # island_tree_02 is ~1.17 × its footprint radius tall
MAX_OBLIQUE_BLOCKED = 0.3  # a street tree may hide at most 30 % of the 05/06 sightlines
TREE_BASE_SCALE = 1.8  # island_tree_02 is ~3.4 m tall; street trees ~5-7 m
PARK_ROWS = (4.0, 11.0)  # metres behind the park's road edge
PARK_SPACING, PARK_JITTER = 7.0, 1.0


@dataclass(frozen=True)
class AssetPlacement:
    name: str
    collection: str
    model: str
    location: tuple[float, float, float]
    rotation_z: float
    scale: float
    # Upper bounds Blender enforces by shrinking the model (never enlarging it): the footprint
    # fits a circle of this diameter at any rotation, and the top stays below this height.
    fit_diameter: float | None = None
    fit_height: float | None = None


def _pots(p) -> list[tuple[float, float, float]]:
    if p.template != "modern_townhouse":
        return []  # ponytail: classic balconies are iron/balustrade, no flat slab for pots yet
    m = p.modern
    half = m.footprint_width.value / 2
    out = []
    for bal in m.balconies:
        n = bal.floor.value
        x0 = -half + bal.offset.value
        y = floor_front_y(p, n) - bal.depth.value + POT_INSET
        z = floor_base_z(m, n)
        out += [(x0 + POT_INSET, y, z), (x0 + bal.width.value - POT_INSET, y, z)]
    for n in range(1, len(m.floors)):
        yf = floor_front_y(p, n)
        if floor_front_y(p, n + 1) > yf:  # terrace on top of floor n
            z = floor_base_z(m, n) + m.floors[n - 1].height.value
            y = yf + TERRACE_POT_BACK
            out += [(-half + TERRACE_POT_SIDE, y, z), (half - TERRACE_POT_SIDE, y, z)]
    return out


def _street_xs(half: float, first: float, spacing: float) -> list[float]:
    xs, x = [], half + first
    while x <= STREET_HALF_LENGTH - 1.0:
        xs += [-x, x]
        x += spacing
    return sorted(xs)


def _park_trees(p, rng: random.Random) -> list[tuple[float, float]]:
    c = p.context
    half = p.site.width.value / 2
    edge = -c.sidewalk_width.value - c.road_width.value
    out = []
    for row in PARK_ROWS:
        if row >= PARK_DEPTH:
            continue
        x = -STREET_HALF_LENGTH + 3.0
        while x <= STREET_HALF_LENGTH - 3.0:
            jx, jy = rng.uniform(-PARK_JITTER, PARK_JITTER), rng.uniform(-PARK_JITTER, PARK_JITTER)
            if abs(x + jx) >= half + LOT_CLEARANCE:
                out.append((x + jx, edge - row + jy))
            x += PARK_SPACING
    return out


def _front_sightlines(p) -> dict[str, list[tuple[tuple, tuple]]]:
    """Per front camera, its (camera, facade point) segments."""
    from exterior_agent.geometry.cameras import fit_cameras  # avoid an import cycle
    from exterior_agent.geometry.scene_plan import template_bounds

    m = p.body
    w = m.footprint_width.value
    cams = {c.id: c.location for c in fit_cameras(*template_bounds(p)) if c.id in FRONT_VIEWS}
    targets = [
        (x, floor_front_y(p, n) - 0.05, floor_base_z(m, n) + m.floors[n - 1].height.value / 2)
        for n in range(1, len(m.floors) + 1)
        for x in (-w / 4, 0.0, w / 4)
    ]
    return {cid: [(c, t) for t in targets] for cid, c in cams.items()}


def _blocks(c, t, x: float, y: float, r: float, h: float, steps: int = 200) -> bool:
    """Does a tree (thin trunk up to the canopy base, canopy cylinder above) cross c→t?"""
    base = CANOPY_BASE * h
    for k in range(steps + 1):
        u = k / steps
        px, py, pz = (c[i] + u * (t[i] - c[i]) for i in range(3))
        d2 = (px - x) ** 2 + (py - y) ** 2
        if (pz < base and d2 < TRUNK_RADIUS**2) or (base <= pz < h and d2 < r * r):
            return True
    return False


def _fits_views(sightlines, x: float, y: float, r: float, h: float) -> bool:
    """Never in front of the facade in 01; at most a share of the 05/06 sightlines."""
    if any(_blocks(c, t, x, y, r, h) for c, t in sightlines.get("01_front", [])):
        return False
    oblique = [s for cid in ("05_front_left", "06_front_right") for s in sightlines.get(cid, [])]
    blocked = sum(_blocks(c, t, x, y, r, h) for c, t in oblique)
    return blocked <= MAX_OBLIQUE_BLOCKED * len(oblique)


def _tree_size(sightlines, x: float, y: float, r_max: float) -> float | None:
    """Largest canopy radius (0.5 m steps) that keeps the facade in view, or None."""
    r = r_max
    while r >= TREE_MIN_RADIUS - 1e-9:
        if _fits_views(sightlines, x, y, r, tree_height(r)):
            return r
        r -= 0.5
    return None


def tree_height(r: float) -> float:
    return min(TREE_MAX_HEIGHT, TREE_HEIGHT_RATIO * r)


def _yard_tree(p) -> tuple[tuple[float, float, float], float] | None:
    """Garden yard: one tree between the side boundary and the walkway, or none if no room."""
    if p.body.front_yard.kind.value != "garden":
        return None
    half, fs = p.site.width.value / 2, p.site.front_setback.value
    r = min(YARD_TREE_MAX_RADIUS, (half - YARD_WALKWAY) / 2, fs / 2 - YARD_MARGIN)
    if r < 0.5:
        return None
    return (-(half + YARD_WALKWAY) / 2, fs / 2, 0.0), r


def context_asset_specs(p) -> list[AssetPlacement]:
    c = p.context
    if c is None:
        return []
    rng = random.Random(c.neighbours.seed.value if c.neighbours is not None else 0)
    half, sw = p.site.width.value / 2, c.sidewalk_width.value
    out: list[AssetPlacement] = []

    def add(name, collection, model, loc, k, scale=1.0, fit=(None, None)):
        turn = round(k * PLANT_TURN, 6)
        out.append(AssetPlacement(name, collection, model, loc, turn, scale, *fit))

    if c.pots.value:
        for k, loc in enumerate(_pots(p), start=1):
            add(f"Pot_{k}", "Plants", c.models.pot.value, loc, k, fit=POT_FIT)
    if c.street_trees.value:
        tree = c.models.tree.value
        if c.front.value == "road":
            spots = [
                (x, -sw + TREE_KERB_OFFSET) for x in _street_xs(half, TREE_FIRST, TREE_SPACING)
            ]
        else:
            spots = _park_trees(p, rng)
        sightlines = _front_sightlines(p)
        k = 0
        for x, y in spots:
            scale = round(TREE_BASE_SCALE * rng.uniform(0.85, 1.15), 3)
            r_max = min(TREE_MAX_RADIUS, abs(x) - half - LOT_MARGIN)  # never into the lot
            r = _tree_size(sightlines, x, y, r_max)
            if r is None:
                continue
            k += 1
            add(f"Tree_{k}", "Context", tree, (x, y, 0.0), k, scale, (2 * r, tree_height(r)))
        yard = _yard_tree(p)
        if yard is not None:
            loc, r = yard
            add("Tree_Yard", "Context", tree, loc, 0, 1.0, (2 * r, YARD_TREE_HEIGHT))
    if c.street_lamps.value:
        for k, x in enumerate(_street_xs(half, LAMP_FIRST, LAMP_SPACING), start=1):
            add(f"Lamp_{k}", "Context", c.models.lamp.value, (x, -sw + LAMP_KERB_OFFSET, 0.0), k)
    return out

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
TREE_SPACING, TREE_FIRST, TREE_KERB_OFFSET = 8.0, 3.0, 0.8
LAMP_SPACING, LAMP_FIRST, LAMP_KERB_OFFSET = 20.0, 7.0, 0.4
LOT_CLEARANCE = 1.0  # street trees/lamps keep |x| >= W/2 + this
YARD_TREE_SIDE, YARD_TREE_SCALE = 0.8, 1.0  # native ~3.4 m fits a 4-5 m yard
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


def _pots(p) -> list[tuple[float, float, float]]:
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


def context_asset_specs(p) -> list[AssetPlacement]:
    c = p.context
    if c is None:
        return []
    rng = random.Random(c.neighbours.seed.value if c.neighbours is not None else 0)
    half, sw = p.site.width.value / 2, c.sidewalk_width.value
    out: list[AssetPlacement] = []

    def add(name, collection, model, loc, k, scale=1.0):
        out.append(AssetPlacement(name, collection, model, loc, round(k * PLANT_TURN, 6), scale))

    if c.pots.value:
        for k, loc in enumerate(_pots(p), start=1):
            add(f"Pot_{k}", "Plants", c.models.pot.value, loc, k)
    if c.street_trees.value:
        tree = c.models.tree.value
        if c.front.value == "road":
            spots = [
                (x, -sw + TREE_KERB_OFFSET) for x in _street_xs(half, TREE_FIRST, TREE_SPACING)
            ]
        else:
            spots = _park_trees(p, rng)
        for k, (x, y) in enumerate(spots, start=1):
            scale = round(TREE_BASE_SCALE * rng.uniform(0.85, 1.15), 3)
            add(f"Tree_{k}", "Context", tree, (x, y, 0.0), k, scale)
        if p.modern.front_yard.kind.value == "garden":
            loc = (-half + YARD_TREE_SIDE, p.site.front_setback.value / 2, 0.0)
            add("Tree_Yard", "Context", tree, loc, 0, YARD_TREE_SCALE)
    if c.street_lamps.value:
        for k, x in enumerate(_street_xs(half, LAMP_FIRST, LAMP_SPACING), start=1):
            add(f"Lamp_{k}", "Context", c.models.lamp.value, (x, -sw + LAMP_KERB_OFFSET, 0.0), k)
    return out

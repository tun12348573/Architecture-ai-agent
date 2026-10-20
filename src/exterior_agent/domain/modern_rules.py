"""Semantic checks for modern_townhouse projects (shape/type checks are done by Pydantic)."""

from exterior_agent.domain.validate_common import (
    MIN_INTERIOR,
    MIN_LINTEL,
    MIN_PIER,
    TOL,
    ValidationIssue,
)

MAX_FLOORS = 5
MAX_TOTAL_HEIGHT = 25.0
MIN_CLEAR = 2.4
MIN_FLOOR_DEPTH = 2.0
CAR_LENGTH = 4.4
CAR_WIDTH = 1.8
MAX_MOTORBIKES = 4
BIKE_LENGTH, BIKE_WIDTH, BIKE_GAP = 1.9, 0.7, 0.05
MODERN_MATERIAL_ROLES = (
    "frame",
    "aluminium",
    "louver",
    "terrace_floor",
    "paving",
    "grass",
    "soil",
    "pergola_wood",
    "props",
)
CONTEXT_MATERIAL_ROLES = ("asphalt", "sidewalk", "kerb", "road_marking", "neighbour_glass")
MAX_NEIGHBOURS_PER_SIDE = 4
MIN_FURNISHED_SIDEWALK = 1.5  # kerb + tree pits / lamp posts


def total_height(m) -> float:
    above_roof = max(m.roof.parapet_height.value, m.roof.stair_head.height.value)
    return sum(f.height.value for f in m.floors) + above_roof


def cladding_top(m) -> float:
    """Top of the ground-floor cladding: under the canopy if there is one, else floor 1's top."""
    top = m.floors[0].height.value
    return min(top, m.canopy.height.value) if m.canopy is not None else top


def check_context(p) -> list[ValidationIssue]:
    """Street context and cladding rules (context geometry itself never enters the lot)."""
    issues: list[ValidationIssue] = []

    def add(path: str, message: str) -> None:
        issues.append(ValidationIssue(path, message))

    m, c = p.body, p.context
    if getattr(m, "cladding", None) is not None:
        if m.cladding.zone.value != "ground_front":
            add("modern.cladding.zone", "zone must be 'ground_front'")
        if p.materials.cladding is None:
            add("materials.cladding", "material role required by modern.cladding")
        top = cladding_top(m)
        for o in m.floors[0].openings_front:
            if o.sill.value + o.height.value > top - MIN_LINTEL + TOL:
                add("modern.cladding", f"cladding top {top:g} m leaves no {MIN_LINTEL} m "
                    f"lintel above opening {o.id}")  # fmt: skip
    if c is None:
        return issues
    if (c.street_trees.value or c.street_lamps.value) and (
        c.sidewalk_width.value < MIN_FURNISHED_SIDEWALK - TOL
    ):
        add("context.sidewalk_width", f"street trees/lamps need a sidewalk of at least "
            f"{MIN_FURNISHED_SIDEWALK} m")  # fmt: skip
    if c.front.value not in ("road", "park"):
        add("context.front", "front must be 'road' or 'park'")
    roles = list(CONTEXT_MATERIAL_ROLES)
    if c.neighbours is not None:
        roles.append("neighbour_wall")
        if not 0 <= c.neighbours.per_side.value <= MAX_NEIGHBOURS_PER_SIDE:
            add("context.neighbours.per_side", f"per_side must be 0..{MAX_NEIGHBOURS_PER_SIDE}")
        if c.neighbours.seed.value < 0:
            add("context.neighbours.seed", "seed must be 0 or more")
    for role in roles:
        if getattr(p.materials, role) is None:
            add(f"materials.{role}", "material role required by context")
    return issues


def check_assets(p) -> list[ValidationIssue]:
    """Asset ids named by the project must exist in the catalog with the right kind."""
    from exterior_agent.assets.catalog import load_catalog

    try:
        catalog = load_catalog()
    except (OSError, ValueError) as exc:
        return [ValidationIssue("materials", f"asset catalog unreadable: {exc}")]
    wanted: list[tuple[str, str, str]] = []
    for role in type(p.materials).model_fields:
        mat = getattr(p.materials, role)
        if mat is not None and mat.value.texture is not None:
            wanted.append((f"materials.{role}.value.texture", mat.value.texture, "texture"))
    if p.world is not None:
        wanted.append(("world.hdri", p.world.hdri.value, "hdri"))
    if p.context is not None:
        for slot in ("tree", "lamp", "pot"):
            model = getattr(p.context.models, slot)
            wanted.append((f"context.models.{slot}", model.value, "model"))
    garden = getattr(p.body.roof, "garden", None)
    for i, model in enumerate(garden.plant_models if garden is not None else []):
        wanted.append((f"modern.roof.garden.plant_models[{i}]", model.value, "model"))
    issues = []
    for path, asset_id, kind in wanted:
        try:
            found = catalog.get(asset_id).kind
        except KeyError:
            issues.append(
                ValidationIssue(path, f"asset {asset_id!r} is not in assets/catalog.json")
            )
            continue
        if found != kind:
            issues.append(ValidationIssue(path, f"asset {asset_id!r} is a {found}, not a {kind}"))
    if p.world is not None:
        if not 0 < p.world.strength.value <= 10:
            issues.append(ValidationIssue("world.strength", "must be in (0, 10]"))
        if not 0 <= p.world.rotation_deg.value < 360:
            issues.append(ValidationIssue("world.rotation_deg", "must be in [0, 360)"))
    return issues


def check_modern(p) -> list[ValidationIssue]:  # noqa: C901 - one flat list of rules
    issues: list[ValidationIssue] = []

    def add(path: str, message: str) -> None:
        issues.append(ValidationIssue(path, message))

    m, s = p.modern, p.site
    fw, fd = m.footprint_width.value, m.footprint_depth.value
    t, slab = m.wall_thickness.value, m.slab_thickness.value

    for role in MODERN_MATERIAL_ROLES:
        if getattr(p.materials, role) is None:
            add(f"materials.{role}", "material role required by modern_townhouse")

    if fw > s.width.value + TOL:
        add("site.width", f"footprint width {fw} m exceeds site width {s.width.value} m")
    needed = s.front_setback.value + fd + s.rear_setback.value
    if needed > s.depth.value + TOL:
        add("site.depth", f"setbacks + footprint depth = {needed:g} m exceed site depth")
    if 2 * t + MIN_INTERIOR > min(fw, fd) + TOL:
        add("modern.wall_thickness", f"walls leave less than {MIN_INTERIOR} m interior")

    floors = m.floors
    n = len(floors)
    if not 1 <= n <= MAX_FLOORS:
        add("modern.floors", f"{n} floors; supported 1..{MAX_FLOORS}")
        return issues
    height = total_height(m)
    if height > MAX_TOTAL_HEIGHT + TOL:
        add("modern.floors", f"total height {height:.3f} m exceeds {MAX_TOTAL_HEIGHT} m")

    setbacks = [f.front_setback.value for f in floors]
    seen: set[str] = set()
    for i, f in enumerate(floors):
        base = f"modern.floors[{i}]"
        clear = f.height.value - slab
        if clear < MIN_CLEAR - TOL:
            add(f"{base}.height", f"clear height {clear:g} m below {MIN_CLEAR} m")
        if i == 0 and setbacks[0] > TOL:
            add(f"{base}.front_setback", "floor 1 cannot be set back")
        if i > 0 and setbacks[i] < setbacks[i - 1] - TOL:
            add(f"{base}.front_setback", "upper floors may only step back further")
        if fd - setbacks[i] < MIN_FLOOR_DEPTH - TOL:
            add(f"{base}.front_setback", f"leaves less than {MIN_FLOOR_DEPTH} m floor depth")
        if f.terrace_pergola is not None and f.terrace_pergola.value:
            if i == len(floors) - 1 or floors[i + 1].front_setback.value <= setbacks[i] + TOL:
                add(f"{base}.terrace_pergola", "no terrace here: the floor above is not set back")
        for side in ("front", "rear"):
            openings = getattr(f, f"openings_{side}")
            spans = []
            for j, o in enumerate(openings):
                op = f"{base}.openings_{side}[{j}]"
                if o.id in seen:
                    add(f"{op}.id", f"duplicate opening id {o.id!r}")
                seen.add(o.id)
                off, w = o.offset.value, o.width.value
                if off < t - TOL:
                    add(f"{op}.offset", f"must be at least {t} m from the corner")
                if off + w > fw - t + TOL:
                    add(f"{op}.width", "opening runs past the facade end")
                if o.sill.value + o.height.value > clear - MIN_LINTEL + TOL:
                    add(f"{op}.height", f"leaves less than {MIN_LINTEL} m lintel")
                if o.kind in ("door", "door_4leaf") and abs(o.sill.value) > TOL:
                    add(f"{op}.sill", "door sill must be 0")
                if o.kind == "window" and o.sill.value <= 0:
                    add(f"{op}.sill", "window sill must be greater than 0")
                if o.kind == "door_4leaf":
                    tr = o.transom_height
                    if tr is None or not 0 < tr.value < o.height.value - TOL:
                        add(f"{op}.transom_height", "door_4leaf needs 0 < transom < height")
                spans.append((off, off + w, f"{op}"))
            spans.sort()
            for (_, end, _), (start, _, op) in zip(spans, spans[1:], strict=False):
                if start - end < MIN_PIER - TOL:
                    add(op, f"needs at least {MIN_PIER} m pier to the previous opening")

    def face_y(floor_no: int) -> float:
        return s.front_setback.value + setbacks[floor_no - 1]

    for i, b in enumerate(m.balconies):
        base = f"modern.balconies[{i}]"
        if not 2 <= b.floor.value <= n:
            add(f"{base}.floor", f"balcony floor must be 2..{n}")
            continue
        if b.offset.value + b.width.value > fw + TOL:
            add(f"{base}.width", "balcony runs past the facade")
        if face_y(b.floor.value) - b.depth.value < -TOL:
            add(f"{base}.depth", "balcony projects past the front boundary")

    for i, fr in enumerate(m.frames):
        base = f"modern.frames[{i}]"
        a, b = fr.from_floor.value, fr.to_floor.value
        if not 1 <= a <= b <= n:
            add(f"{base}.from_floor", f"need 1 <= from_floor <= to_floor <= {n}")
            continue
        if len({setbacks[k - 1] for k in range(a, b + 1)}) > 1:
            add(base, "framed floors must share one front setback")
        if face_y(a) - fr.depth.value < -TOL:
            add(f"{base}.depth", "frame projects past the front boundary")
        if 2 * fr.thickness.value >= fw:
            add(f"{base}.thickness", "frame posts fill the whole facade")

    for i, lv in enumerate(m.louvers):
        base = f"modern.louvers[{i}]"
        if not 1 <= lv.floor.value <= n:
            add(f"{base}.floor", f"louver floor must be 1..{n}")
        if lv.offset.value < t - TOL:
            add(f"{base}.offset", f"must be at least {t} m from the corner")
        if lv.offset.value + lv.width.value > fw - t + TOL:
            add(f"{base}.width", "louvers run past the facade")
        if lv.count.value < 2:
            add(f"{base}.count", "need at least 2 blades")

    if m.canopy is not None:
        c = m.canopy
        tops = [o.sill.value + o.height.value for o in floors[0].openings_front]
        if tops and c.height.value < max(tops) - TOL:
            add("modern.canopy.height", "canopy is lower than a ground-floor front opening")
        if c.height.value + c.thickness.value > floors[0].height.value + TOL:
            add("modern.canopy.height", "canopy is above floor 1")
        if c.depth.value > s.front_setback.value + TOL:
            add("modern.canopy.depth", "canopy projects past the front boundary")

    r = m.roof
    pt = r.parapet_thickness.value
    sh = r.stair_head
    if sh.width.value > fw - 2 * pt + TOL:
        add("modern.roof.stair_head.width", "stair head wider than the roof inside the parapet")
    roof_depth = fd - setbacks[-1] - 2 * pt
    if r.garden is not None:
        roof_depth -= r.garden.planter_width.value
    if sh.depth.value > roof_depth + TOL:
        add("modern.roof.stair_head.depth", "stair head does not fit behind the roof garden")
    if sh.height.value < 2.0:
        add("modern.roof.stair_head.height", "stair head lower than 2.0 m")

    y = m.front_yard
    if y.kind.value not in ("parking", "garden"):
        add("modern.front_yard.kind", "kind must be 'parking' or 'garden'")
    if y.gate_width.value > s.width.value + TOL:
        add("modern.front_yard.gate_width", "gate wider than the site")
    if y.car.value and (
        y.kind.value != "parking" or s.front_setback.value < CAR_LENGTH + 0.1 - TOL
    ):
        add("modern.front_yard.car", f"car needs a parking yard at least {CAR_LENGTH + 0.1} m deep")
    bikes = y.motorbikes.value
    if not 0 <= bikes <= MAX_MOTORBIKES:
        add("modern.front_yard.motorbikes", f"0..{MAX_MOTORBIKES} motorbikes")
    else:
        pitch = BIKE_WIDTH + BIKE_GAP
        if y.car.value:  # bikes alternate either side of the centred car
            fits = CAR_WIDTH / 2 + -(-bikes // 2) * pitch <= s.width.value / 2 + TOL
        else:
            fits = bikes * pitch - BIKE_GAP <= s.width.value + TOL
        if bikes and not fits:
            add("modern.front_yard.motorbikes", "motorbikes do not fit across the front yard")
    return issues + check_context(p) + check_assets(p)

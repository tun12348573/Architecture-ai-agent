"""Semantic checks for neoclassical_townhouse projects (shape/type checks are done by Pydantic)."""

import math

from exterior_agent.domain.validate_common import (
    MIN_LINTEL,
    MIN_PIER,
    TOL,
    ValidationIssue,
)

MAX_FLOORS = 4
MAX_TOTAL_HEIGHT = 25.0
MIN_CLEAR = 2.4
PITCH_RANGE = (25.0, 55.0)
OCULUS_HEIGHT = 0.4  # oculus centre, as a fraction of the gable height
OCULUS_MARGIN = 0.1
COLUMN_CLEARANCE = 0.05  # column centre sits radius + this inside the bay edge
PEDIMENT_CLEARANCE = 0.05
REQUIRED_ROLES = ("wall", "window_glass", "frame", "trim", "panel", "roof_tiles", "iron",
                  "door_wood", "paving", "grass")  # fmt: skip


def gable_height(m) -> float:
    return m.footprint_width.value / 2 * math.tan(math.radians(m.roof.pitch_deg.value))


def ridge_height(m) -> float:
    return sum(f.height.value for f in m.floors) + gable_height(m) + m.roof.thickness.value


def oculus_limit(m) -> float:
    """Largest oculus radius that stays inside the front gable (with a margin)."""
    w2, h = m.footprint_width.value / 2, gable_height(m)
    h0 = OCULUS_HEIGHT * h
    to_slope = (1 - h0 / h) / math.hypot(1 / w2, 1 / h)
    return min(to_slope, h0) - OCULUS_MARGIN


def bay_range(m) -> tuple[float, float]:
    """Bay x-range as facade offsets (0 = left edge seen from the street)."""
    b, w = m.bay, m.footprint_width.value
    return (0.0, b.width.value) if b.side.value == "left" else (w - b.width.value, w)


def column_ranges(m) -> list[tuple[float, float]]:
    x0, x1 = bay_range(m)
    r = m.bay.column_radius.value
    centres = (x0 + r + COLUMN_CLEARANCE, x1 - r - COLUMN_CLEARANCE)
    return [(c - r, c + r) for c in centres]


def check_classic(p) -> list[ValidationIssue]:  # noqa: C901 - one flat list of rules
    issues: list[ValidationIssue] = []

    def add(path: str, message: str) -> None:
        issues.append(ValidationIssue(path, message))

    m, s = p.classic, p.site
    fw, fd, t = m.footprint_width.value, m.footprint_depth.value, m.wall_thickness.value
    for role in REQUIRED_ROLES:
        if getattr(p.materials, role) is None:
            add(f"materials.{role}", "material role required by neoclassical_townhouse")
    if fw > s.width.value + TOL:
        add("site.width", f"footprint width {fw} m exceeds site width {s.width.value} m")
    if s.front_setback.value + fd + s.rear_setback.value > s.depth.value + TOL:
        add("site.depth", "setbacks + footprint depth exceed site depth")
    n = len(m.floors)
    if not 1 <= n <= MAX_FLOORS:
        add("classic.floors", f"{n} floors; supported 1..{MAX_FLOORS}")
        return issues

    pitch = m.roof.pitch_deg.value
    if not PITCH_RANGE[0] <= pitch <= PITCH_RANGE[1]:
        add("classic.roof.pitch_deg", f"pitch must be {PITCH_RANGE[0]:g}..{PITCH_RANGE[1]:g}°")
    elif ridge_height(m) > MAX_TOTAL_HEIGHT + TOL:
        add("classic.floors", f"ridge at {ridge_height(m):.2f} m exceeds {MAX_TOTAL_HEIGHT:g} m")
    elif m.roof.gable_front.oculus_radius.value > oculus_limit(m) + TOL:
        add("classic.roof.gable_front.oculus_radius", f"oculus does not fit in the gable "
            f"(max {oculus_limit(m):.2f} m)")  # fmt: skip

    seen: set[str] = set()
    for i, f in enumerate(m.floors):
        base = f"classic.floors[{i}]"
        clear = f.height.value - m.slab_thickness.value
        if clear < MIN_CLEAR - TOL:
            add(f"{base}.height", f"clear height {clear:g} m below {MIN_CLEAR} m")
        for side in ("front", "rear"):
            spans = []
            for j, o in enumerate(getattr(f, f"openings_{side}")):
                op = f"{base}.openings_{side}[{j}]"
                if o.id in seen:
                    add(f"{op}.id", f"duplicate opening id {o.id!r}")
                seen.add(o.id)
                off, w, h, sill = o.offset.value, o.width.value, o.height.value, o.sill.value
                if off < t - TOL:
                    add(f"{op}.offset", f"must be at least {t} m from the corner")
                if off + w > fw - t + TOL:
                    add(f"{op}.width", "opening runs past the facade end")
                if o.head == "arch" and h <= w / 2 + TOL:
                    add(f"{op}.height", "an arch needs height greater than half its width")
                if sill + h > clear - MIN_LINTEL + TOL:
                    add(f"{op}.height", f"leaves less than {MIN_LINTEL} m lintel")
                if o.kind in ("door", "door_wood") and abs(sill) > TOL:
                    add(f"{op}.sill", "door sill must be 0")
                if o.kind == "window" and sill <= 0:
                    add(f"{op}.sill", "window sill must be greater than 0")
                if o.balcony is not None and side == "front":
                    if o.balcony.projection.value > s.front_setback.value + TOL:
                        add(f"{op}.balcony.projection", "balcony projects past the front boundary")
                spans.append((off, off + w, op))
            spans.sort()
            for (_, end, _), (start, _, op) in zip(spans, spans[1:], strict=False):
                if start - end < MIN_PIER - TOL:
                    add(op, f"needs at least {MIN_PIER} m pier to the previous opening")

    b = m.bay
    if b is not None:
        if b.side.value not in ("left", "right"):
            add("classic.bay.side", "side must be 'left' or 'right'")
            return issues
        if b.width.value > fw - TOL:
            add("classic.bay.width", "bay is as wide as the facade")
        if b.projection.value > s.front_setback.value + TOL:
            add("classic.bay.projection", "bay projects past the front boundary")
        a, z = b.from_floor.value, b.to_floor.value
        if not 2 <= a <= z <= n:
            add("classic.bay.from_floor", f"need 2 <= from_floor <= to_floor <= {n}")
            return issues
        x0, x1 = bay_range(m)
        if b.columns.value:
            cols = column_ranges(m)
            for j, o in enumerate(m.floors[a - 1].openings_front):
                lo, hi = o.offset.value, o.offset.value + o.width.value
                if any(lo < c1 - TOL and hi > c0 + TOL for c0, c1 in cols):
                    add(f"classic.floors[{a - 1}].openings_front[{j}]", "opening hits a column")
        if b.pediment is not None:
            ph = b.pediment.height.value
            if z == n:
                add("classic.bay.pediment.height", "a pediment needs a floor above the bay")
            else:
                for o in m.floors[z].openings_front:
                    lo, hi = o.offset.value, o.offset.value + o.width.value
                    inside = lo < x1 - TOL and hi > x0 + TOL
                    if inside and o.sill.value < ph + PEDIMENT_CLEARANCE - TOL:
                        add("classic.bay.pediment.height", f"pediment reaches opening {o.id}")

    y = m.front_yard
    if y.kind.value not in ("parking", "garden"):
        add("classic.front_yard.kind", "kind must be 'parking' or 'garden'")
    if y.gate_width.value > s.width.value + TOL:
        add("classic.front_yard.gate_width", "gate wider than the site")
    return issues

"""Load, normalize (to metres) and semantically check project.json."""

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from exterior_agent.domain.classic_rules import check_classic
from exterior_agent.domain.modern_rules import check_assets, check_context, check_modern
from exterior_agent.domain.project import (
    CANONICAL_CAMERA_IDS,
    Length,
    Original,
    Project,
)
from exterior_agent.domain.units import to_metres
from exterior_agent.domain.validate_common import (  # noqa: F401 - re-exported
    MIN_INTERIOR,
    MIN_LINTEL,
    MIN_PIER,
    TOL,
    ValidationIssue,
)

MAX_ROOF_THICKNESS = 1.0
# Lengths that may legitimately be zero; every other length must be positive.
ZERO_ALLOWED = {"offset", "sill"}


class ProjectValidationError(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(f"{i.path}: {i.message}" for i in issues))


def load_project(path: Path) -> Project:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProjectValidationError([ValidationIssue("$", f"invalid JSON: {exc}")]) from exc
    return parse_project(data)


def parse_project(data: object) -> Project:
    if not isinstance(data, dict):
        raise ProjectValidationError(
            [ValidationIssue("$", "top-level JSON value must be an object")]
        )
    try:
        project = Project.model_validate(data)
    except ValidationError as exc:
        raise ProjectValidationError(
            [ValidationIssue(_loc_path(e["loc"]), e["msg"]) for e in exc.errors()]
        ) from exc
    project = _normalize(project)
    issues = check_semantics(project)
    if issues:
        raise ProjectValidationError(issues)
    return project


def _loc_path(loc: tuple) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "$"


def _normalize(node):
    if isinstance(node, Length):
        if node.unit == "m":  # already metres; keep an existing conversion record
            original = node.original or Original(value=node.value, unit="m")
            return node.model_copy(update={"original": original})
        return node.model_copy(
            update={
                "value": to_metres(node.value, node.unit),
                "unit": "m",
                "original": Original(value=node.value, unit=node.unit),
            }
        )
    if isinstance(node, BaseModel):
        updates = {name: _normalize(getattr(node, name)) for name in type(node).model_fields}
        return node.model_copy(update=updates)
    if isinstance(node, list):
        return [_normalize(v) for v in node]
    return node


def _walk_lengths(node, path=""):
    if isinstance(node, Length):
        yield path, node
    elif isinstance(node, BaseModel):
        for name in type(node).model_fields:
            yield from _walk_lengths(getattr(node, name), f"{path}.{name}" if path else name)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_lengths(v, f"{path}[{i}]")


def facade_length(project: Project, wall: str) -> float:
    b = project.building
    return b.footprint_width.value if wall in ("front", "rear") else b.footprint_depth.value


def _template_issues(p: Project) -> list[ValidationIssue]:
    if p.template == "modern_townhouse":
        if (p.schema_version != "1.1" or p.modern is None or p.building is not None
                or p.classic is not None):  # fmt: skip
            return [
                ValidationIssue(
                    "template",
                    "modern_townhouse needs schema_version 1.1, a 'modern' block and no 'building'",
                )
            ]
    elif p.template == "neoclassical_townhouse":
        if (p.schema_version != "1.1" or p.classic is None or p.building is not None
                or p.modern is not None):  # fmt: skip
            return [
                ValidationIssue(
                    "template",
                    "neoclassical_townhouse needs schema_version 1.1, a 'classic' block, "
                    "no 'modern' and no 'building'",
                )
            ]
    elif p.building is None or p.modern is not None or p.classic is not None:
        return [ValidationIssue("template", "basic_house needs a 'building' block and no 'modern'")]
    elif p.world is not None or any(
        m is not None and m.value.texture is not None
        for m in (getattr(p.materials, r) for r in type(p.materials).model_fields)
    ):
        return [ValidationIssue("template", "textures and HDRI worlds need modern_townhouse")]
    elif p.context is not None:
        return [ValidationIssue("template", "a street context needs a townhouse template")]
    return []


def _zero_allowed(path: str) -> bool:
    last = path.rsplit(".", 1)[-1]
    return last in ZERO_ALLOWED or (path.startswith("modern.floors") and last == "front_setback")


def check_semantics(p: Project) -> list[ValidationIssue]:
    issues = _template_issues(p)
    if issues:
        return issues
    add = lambda path, msg: issues.append(ValidationIssue(path, msg))  # noqa: E731

    if p.input_mode != "parameters":
        add("input_mode", f"input_mode {p.input_mode!r} is not supported in M1")
    ids = [c.id for c in p.cameras]
    if sorted(ids) != sorted(CANONICAL_CAMERA_IDS):
        add("cameras", f"M1 requires exactly the canonical cameras {list(CANONICAL_CAMERA_IDS)}")
    if p.template == "basic_house":
        b = p.building
        if b.floors.value != 1:
            add("building.floors", f"{b.floors.value} floors is not supported in M1 (exactly 1)")
        if b.roof.type.value != "flat":
            add("building.roof.type", f"roof type {b.roof.type.value!r} is not supported in M1")

    for path, length in _walk_lengths(p):
        if length.value <= 0 and not _zero_allowed(path):
            add(path, "must be greater than zero")
    if issues:
        return issues
    if p.template == "modern_townhouse":
        issues = check_modern(p)
        if issues:
            return issues
        # Imported here: geometry depends on the domain package (avoid an import cycle).
        from exterior_agent.geometry.modern_checks import check_modern_geometry

        return check_modern_geometry(p)
    if p.template == "neoclassical_townhouse":
        return check_classic(p) + check_context(p) + check_assets(p)
    return _check_basic(p)


def _check_basic(p: Project) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    add = lambda path, msg: issues.append(ValidationIssue(path, msg))  # noqa: E731
    b, s = p.building, p.site

    fw, fd, t, h = (
        b.footprint_width.value,
        b.footprint_depth.value,
        b.wall_thickness.value,
        (b.wall_height.value),
    )
    if fw > s.width.value + TOL:
        add("site.width", f"footprint width {fw} m exceeds site width {s.width.value} m")
    needed = s.front_setback.value + fd + s.rear_setback.value
    if needed > s.depth.value + TOL:
        add(
            "site.depth",
            f"front setback + footprint depth + rear setback = {needed:g} m "
            f"exceeds site depth {s.depth.value} m",
        )
    if 2 * t + MIN_INTERIOR > min(fw, fd) + TOL:
        add("building.wall_thickness", f"walls leave less than {MIN_INTERIOR} m interior")
    if b.roof.thickness.value > MAX_ROOF_THICKNESS + TOL:
        add("building.roof.thickness", f"must be at most {MAX_ROOF_THICKNESS} m")

    seen: set[str] = set()
    for i, o in enumerate(b.openings):
        base = f"building.openings[{i}]"
        if o.id in seen:
            add(f"{base}.id", f"duplicate opening id {o.id!r}")
        seen.add(o.id)
        length = facade_length(p, o.wall)
        if o.offset.value < t - TOL:
            add(f"{base}.offset", f"must be at least the wall thickness {t} m from the corner")
        if o.offset.value + o.width.value > length - t + TOL:
            add(f"{base}.width", f"opening runs past the {o.wall} facade end (corner {t} m)")
        top = o.sill.value + o.height.value
        if top > h - MIN_LINTEL + TOL:
            add(f"{base}.height", f"sill + height {top:g} m leaves less than {MIN_LINTEL} m lintel")
        if o.kind == "door" and abs(o.sill.value) > TOL:
            add(f"{base}.sill", "door sill must be 0")
        if o.kind == "window" and o.sill.value <= 0:
            add(f"{base}.sill", "window sill must be greater than 0")

    by_wall: dict[str, list[tuple[int, float, float]]] = {}
    for i, o in enumerate(b.openings):
        by_wall.setdefault(o.wall, []).append((i, o.offset.value, o.offset.value + o.width.value))
    for spans in by_wall.values():
        spans.sort(key=lambda span: span[1])
        for (_, _, end), (j, start, _) in zip(spans, spans[1:], strict=False):
            if start - end < MIN_PIER - TOL:
                msg = f"needs at least {MIN_PIER} m pier to the previous opening"
                add(f"building.openings[{j}]", msg)
    return issues


def unresolved_assumptions(project: Project) -> list[str]:
    out: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            if node.get("status") == "needs_review" and "source" in node:
                out.append(path)
                return
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(project.model_dump(mode="json"), "")
    return out

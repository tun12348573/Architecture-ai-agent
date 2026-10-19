"""Load, normalize (to metres) and semantically check project.json."""

import json
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ValidationError

from exterior_agent.domain.project import (
    CANONICAL_CAMERA_IDS,
    Length,
    Original,
    Project,
)
from exterior_agent.domain.units import to_metres

TOL = 0.001
MIN_INTERIOR = 0.5
MIN_LINTEL = 0.10
MIN_PIER = 0.10
MAX_ROOF_THICKNESS = 1.0
# Lengths that may legitimately be zero; every other length must be positive.
ZERO_ALLOWED = {"offset", "sill"}


class ValidationIssue(NamedTuple):
    path: str
    message: str


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
        if node.original is not None:  # already normalized
            return node
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


def check_semantics(p: Project) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    add = lambda path, msg: issues.append(ValidationIssue(path, msg))  # noqa: E731
    b, s = p.building, p.site

    if p.input_mode != "parameters":
        add("input_mode", f"input_mode {p.input_mode!r} is not supported in M1")
    if b.floors.value != 1:
        add("building.floors", f"{b.floors.value} floors is not supported in M1 (exactly 1)")
    if b.roof.type.value != "flat":
        add("building.roof.type", f"roof type {b.roof.type.value!r} is not supported in M1")

    for path, length in _walk_lengths(p):
        if length.value <= 0 and path.rsplit(".", 1)[-1] not in ZERO_ALLOWED:
            add(path, "must be greater than zero")
    if issues:
        return issues

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

    ids = [c.id for c in p.cameras]
    if sorted(ids) != sorted(CANONICAL_CAMERA_IDS):
        add("cameras", f"M1 requires exactly the canonical cameras {list(CANONICAL_CAMERA_IDS)}")
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

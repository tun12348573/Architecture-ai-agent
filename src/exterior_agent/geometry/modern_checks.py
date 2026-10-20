"""Geometric validation of a modern_townhouse project, run after the parameter rules.

Builds every object (pure Python) and rejects combinations whose geometry is impossible:
duplicate object names, objects outside the lot, inverted/zero-size parts (dimensions too
small for the component) and parts passing through each other. Parts may touch.
"""

import itertools

from exterior_agent.domain.validate_common import TOL, ValidationIssue
from exterior_agent.geometry.mesh import Bounds
from exterior_agent.geometry.modern_cladding import cladding_objects
from exterior_agent.geometry.modern_facade import facade_objects
from exterior_agent.geometry.modern_massing import massing_objects
from exterior_agent.geometry.modern_site import site_objects

OVERLAP_EPS = 1e-6  # metres; thinner than this counts as touching
MIN_PART_VOLUME = 1e-12
PATHS = (  # object-name prefix -> parameter block to point the owner at
    ("Balcony_", "modern.balconies"),
    ("Frame_", "modern.frames"),
    ("Louver_", "modern.louvers"),
    ("Canopy", "modern.canopy"),
    ("Prop_", "modern.front_yard"),
    ("Gate", "modern.front_yard"),
    ("Fence_", "modern.front_yard"),
    ("Parapet", "modern.roof"),
    ("StairHead", "modern.roof"),
    ("Planter_", "modern.roof"),
    ("Roof_", "modern.roof"),
)


def _path(name: str) -> str:
    return next((path for prefix, path in PATHS if name.startswith(prefix)), "modern.floors")


def _overlap(a: Bounds, b: Bounds) -> float:
    vol = 1.0
    for k in range(3):
        d = min(a[1][k], b[1][k]) - max(a[0][k], b[0][k])
        if d <= OVERLAP_EPS:
            return 0.0
        vol *= d
    return vol


def _parts(mesh) -> list[tuple[Bounds, float]]:
    """Split a merged box mesh (6 faces per box) into (AABB, signed volume) per box."""
    out = []
    for k in range(0, len(mesh.faces), 6):
        group = mesh.faces[k : k + 6]
        pts = [mesh.vertices[i] for face in group for i in face]
        xs, ys, zs = zip(*pts, strict=True)
        volume = 0.0
        for face in group:
            a = mesh.vertices[face[0]]
            for b, c in zip(face[1:-1], face[2:], strict=True):
                b, c = mesh.vertices[b], mesh.vertices[c]
                volume += (
                    a[0] * (b[1] * c[2] - b[2] * c[1])
                    - a[1] * (b[0] * c[2] - b[2] * c[0])
                    + a[2] * (b[0] * c[1] - b[1] * c[0])
                ) / 6
        out.append((((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))), volume))
    return out


def check_modern_geometry(p) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def add(name: str, message: str) -> None:
        issues.append(ValidationIssue(_path(name), message))

    objects = massing_objects(p) + facade_objects(p) + cladding_objects(p) + site_objects(p)
    names = [o.name for o in objects]
    for name in sorted({n for n in names if names.count(n) > 1}):
        add(name, f"two components produce the same object {name!r} (one per floor/id)")

    half, depth = p.site.width.value / 2, p.site.depth.value
    solids: dict[str, list[Bounds]] = {}
    walls: dict[str, tuple[Bounds, list[Bounds]]] = {}
    holes = [o.empty_box for o in objects if o.mesh is None]
    for o in objects:
        if o.mesh is None or o.name == "Site_Context":
            continue
        (lo, hi) = o.mesh.bounds()
        if lo[0] < -half - TOL or hi[0] > half + TOL or lo[1] < -TOL or hi[1] > depth + TOL:
            add(o.name, f"{o.name} extends outside the lot")
        if len(o.mesh.faces) == 1:  # ground quads have no volume
            continue
        # wall-like solids (holed grid meshes, not merged boxes) = AABB minus openings through it
        if "_Wall_" in o.name or o.name.startswith("Cladding_"):
            inside = [h for h in holes if _overlap(h, (lo, hi)) > 0]
            walls[o.name] = ((lo, hi), inside)
            continue
        parts = _parts(o.mesh)
        if any(volume <= MIN_PART_VOLUME for _, volume in parts):
            add(o.name, f"{o.name} has an inverted or zero-size part: a dimension is too small")
            continue
        boxes = [box for box, _ in parts]
        if any(_overlap(a, b) > 0 for a, b in itertools.combinations(boxes, 2)):
            add(o.name, f"parts of {o.name} pass through each other: a dimension is too small")
        solids[o.name] = boxes

    def volume_between(a: str, b: str) -> float:
        boxes_b = solids[b]
        if a in walls:
            box, cut = walls[a]
            return sum(_overlap(box, x) - sum(_overlap(h, x) for h in cut) for x in boxes_b)
        return sum(_overlap(x, y) for x in solids[a] for y in boxes_b)

    names_solid = list(walls) + list(solids)
    for a, b in itertools.combinations(names_solid, 2):
        if a in walls and b in walls:
            continue  # walls are built not to overlap (side walls fit between front/rear)
        if b in walls:
            a, b = b, a
        v = volume_between(a, b)
        if v > OVERLAP_EPS:
            first = b if a in walls else a
            add(first, f"{a} and {b} pass through each other ({v:.3f} m³)")
    return issues

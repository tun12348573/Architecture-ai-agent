"""Walls and plates with polygon holes (arched and round openings), pure Python, no booleans.

Outlines are lists of (u, z) points in a wall's local plane, counter-clockwise. The solid's
front face lies at v = 0 of the WallFrame (the street side), its back at v = thickness. Holes
touching the outline's first edge (its bottom, e.g. a door sill) are cut into the outline itself;
the others are bridged into it, then the face is ear-clipped.
"""

import math

from exterior_agent.geometry.layout import WallFrame
from exterior_agent.geometry.mesh import Mesh

EPS = 1e-9
Pt = tuple[float, float]


def rect_outline(u0: float, u1: float, z0: float, z1: float) -> list[Pt]:
    return [(u0, z0), (u1, z0), (u1, z1), (u0, z1)]


def arch_outline(u0: float, u1: float, z0: float, z1: float, segments: int = 24) -> list[Pt]:
    """Opening with a semicircular head: crown at z1, springing at z1 - (u1 - u0)/2."""
    r, cu = (u1 - u0) / 2, (u0 + u1) / 2
    zs = max(z0, z1 - r)
    arc = [(cu + r * math.cos(math.pi * k / segments), zs + r * math.sin(math.pi * k / segments))
           for k in range(1, segments)]  # fmt: skip
    return [(u0, z0), (u1, z0), (u1, zs), *arc, (u0, zs)]


def circle_outline(cu: float, cz: float, r: float, segments: int = 32) -> list[Pt]:
    return [(cu + r * math.cos(math.tau * k / segments), cz + r * math.sin(math.tau * k / segments))
            for k in range(segments)]  # fmt: skip


def _cross(o: Pt, a: Pt, b: Pt) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _area(pts: list[Pt]) -> float:
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1], strict=True))


def _cut_sill_holes(outer: list[Pt], holes: list[list[Pt]]) -> tuple[list[Pt], list[list[Pt]]]:
    """Holes whose bottom lies on the outline's first edge become notches in the outline."""
    z_bottom = outer[0][1]
    touching = [h for h in holes if min(p[1] for p in h) <= z_bottom + EPS]
    if not touching:
        return outer, holes
    notch: list[Pt] = []
    for h in sorted(touching, key=lambda h: min(p[0] for p in h)):
        i = min(range(len(h)), key=lambda k: (h[k][1], h[k][0]))  # bottom-left corner
        cw = [h[(i - k) % len(h)] for k in range(len(h))]  # walk up the left side first
        j = max(range(len(cw)), key=lambda k: (cw[k][1] <= z_bottom + EPS, cw[k][0]))
        notch += cw[: j + 1]  # bottom-left ... bottom-right
    return [outer[0], *notch, *outer[1:]], [h for h in holes if h not in touching]


def _segments_cross(a: Pt, b: Pt, c: Pt, d: Pt) -> bool:
    """Proper crossing of segments ab and cd (shared endpoints do not count)."""
    if a in (c, d) or b in (c, d):
        return False
    d1, d2 = _cross(c, d, a), _cross(c, d, b)
    d3, d4 = _cross(a, b, c), _cross(a, b, d)
    return d1 * d2 < -EPS * EPS and d3 * d4 < -EPS * EPS


def _bridge(
    poly: list[int], hole: list[int], pts: list[Pt], blockers: list[list[int]]
) -> list[int]:
    """Splice a clockwise hole into the polygon through the closest mutually visible vertices."""
    m = max(range(len(hole)), key=lambda k: (pts[hole[k]][0], -pts[hole[k]][1]))
    mp = pts[hole[m]]
    loops = [poly, hole, *blockers]
    edges = [(pts[lp[k]], pts[lp[(k + 1) % len(lp)]]) for lp in loops for k in range(len(lp))]
    best = None
    for i, vid in enumerate(poly):
        p = pts[vid]
        if any(_segments_cross(mp, p, a, b) for a, b in edges):
            continue
        dist = (p[0] - mp[0]) ** 2 + (p[1] - mp[1]) ** 2
        if best is None or dist < best[0] - EPS:
            best = (dist, i)
    if best is None:
        raise ValueError("cannot bridge hole into the wall outline")
    i = best[1]
    ring = hole[m:] + hole[: m + 1]
    return poly[: i + 1] + ring + poly[i:]


def _inside_tri(p: Pt, a: Pt, b: Pt, c: Pt) -> bool:
    return _cross(a, b, p) > EPS and _cross(b, c, p) > EPS and _cross(c, a, p) > EPS


def _ear_clip(poly: list[int], pts: list[Pt]) -> list[tuple[int, int, int]]:
    poly = list(poly)
    tris = []
    while len(poly) > 3:
        n = len(poly)
        for k in range(n):
            ia, ib, ic = poly[k - 1], poly[k], poly[(k + 1) % n]
            a, b, c = pts[ia], pts[ib], pts[ic]
            if _cross(a, b, c) <= EPS:
                continue
            corners = {ia, ib, ic}
            if any(v not in corners and pts[v] not in (a, b, c) and _inside_tri(pts[v], a, b, c)
                   for v in poly):  # fmt: skip
                continue
            tris.append((ia, ib, ic))
            del poly[k]
            break
        else:  # no ear: drop a collinear vertex (zero-area corner) and retry
            k = min(range(n), key=lambda k: abs(_cross(pts[poly[k - 1]], pts[poly[k]],
                                                        pts[poly[(k + 1) % n]])))  # fmt: skip
            if abs(_cross(pts[poly[k - 1]], pts[poly[k]], pts[poly[(k + 1) % n]])) > 1e-6:
                raise ValueError("wall outline could not be triangulated")
            del poly[k]
    if len(poly) == 3 and _cross(*(pts[i] for i in poly)) > EPS:
        tris.append(tuple(poly))
    return tris


def prism_with_holes(outer: list[Pt], holes: list[list[Pt]], thickness: float,
                     frame: WallFrame) -> Mesh:  # fmt: skip
    """Closed solid: triangulated front/back faces plus reveals around every hole."""
    outer, inner = _cut_sill_holes(list(outer), [list(h) for h in holes])
    if _area(outer) < 0:
        outer.reverse()
    pts: list[Pt] = []
    index: dict[Pt, int] = {}

    def ids(loop: list[Pt]) -> list[int]:
        out = []
        for p in loop:
            key = (round(p[0], 9) + 0.0, round(p[1], 9) + 0.0)
            if key not in index:
                index[key] = len(pts)
                pts.append(key)
            out.append(index[key])
        return out

    outer_ids = ids(outer)
    hole_ids = []
    for h in inner:
        loop = ids(h)
        if _area([pts[i] for i in loop]) > 0:
            loop.reverse()  # holes run clockwise
        hole_ids.append(loop)
    poly = outer_ids
    pending = sorted(hole_ids, key=lambda h: -max(pts[i][0] for i in h))
    for k, h in enumerate(pending):
        poly = _bridge(poly, h, pts, pending[k + 1 :])
    tris = _ear_clip(poly, pts)

    n = len(pts)
    verts = [frame.to_world(u, 0.0, z) for u, z in pts] + [
        frame.to_world(u, thickness, z) for u, z in pts
    ]
    faces: list[tuple[int, ...]] = []
    for a, b, c in tris:
        faces.append((a, b, c))
        faces.append((n + c, n + b, n + a))
    for loop in [outer_ids, *hole_ids]:
        for a, b in zip(loop, loop[1:] + loop[:1], strict=True):
            faces.append((b, a, n + a, n + b))
    mesh = Mesh(verts, faces)
    return mesh if _volume(mesh) > 0 else Mesh(verts, [tuple(reversed(f)) for f in faces])


def _volume(mesh: Mesh) -> float:
    total = 0.0
    for f in mesh.faces:
        ax, ay, az = mesh.vertices[f[0]]
        for i, j in zip(f[1:-1], f[2:], strict=True):
            bx, by, bz = mesh.vertices[i]
            cx, cy, cz = mesh.vertices[j]
            total += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return total

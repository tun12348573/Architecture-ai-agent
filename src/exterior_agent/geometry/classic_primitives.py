"""Ornament primitives for the neoclassical template (pure Python, deterministic).

Every primitive returns a closed mesh with consistent outward winding, so Blender needs no
normal recalculation and the geometry checks can treat parts as solids.
"""

import math

from exterior_agent.geometry.mesh import Mesh, Vec3
from exterior_agent.geometry.primitives import merge_meshes

TAU = 2 * math.pi
AXIS_EPS = 1e-12

merge = merge_meshes


def _signed_volume(vertices: list[Vec3], faces: list[tuple[int, ...]]) -> float:
    total = 0.0
    for face in faces:
        ax, ay, az = vertices[face[0]]
        for i, j in zip(face[1:-1], face[2:], strict=True):
            bx, by, bz = vertices[i]
            cx, cy, cz = vertices[j]
            total += ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
    return total


def _outward(vertices: list[Vec3], faces: list[tuple[int, ...]]) -> Mesh:
    """Faces are built consistently; flip them all if they wind inward."""
    if _signed_volume(vertices, faces) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return Mesh(vertices, faces)


def _skin(rings: list[list[int]], closed_loop: bool) -> list[tuple[int, ...]]:
    """Quads between consecutive rings (each ring is a closed polygon of vertex indices)."""
    faces = []
    n = len(rings)
    for i in range(n if closed_loop else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        m = len(a)
        for k in range(m):
            k1 = (k + 1) % m
            faces.append((a[k], a[k1], b[k1], b[k]))
    return faces


def lathe(profile, center: Vec3, segments: int = 32, a0: float = 0.0, a1: float = TAU) -> Mesh:
    """Revolve a closed (r, z) profile about the vertical through `center`.

    Profile points with r == 0 become single axis vertices; a partial sweep gets flat end caps.
    """
    cx, cy, cz = center
    full = abs(a1 - a0 - TAU) < 1e-9
    steps = segments if full else segments + 1
    verts: list[Vec3] = []
    idx: list[list[int]] = []  # idx[k][i]: vertex of profile point k at angle step i
    for r, z in profile:
        if r <= AXIS_EPS:
            verts.append((cx, cy, cz + z))
            idx.append([len(verts) - 1] * steps)
            continue
        row = []
        for i in range(steps):
            a = a0 + (a1 - a0) * i / segments
            verts.append((cx + r * math.cos(a), cy + r * math.sin(a), cz + z))
            row.append(len(verts) - 1)
        idx.append(row)
    m = len(profile)
    faces: list[tuple[int, ...]] = []
    for k in range(m):
        k1 = (k + 1) % m
        if profile[k][0] <= AXIS_EPS and profile[k1][0] <= AXIS_EPS:
            continue  # edge along the axis
        lo, hi = idx[k], idx[k1]
        for i in range(segments):
            j = (i + 1) % steps
            face = tuple(dict.fromkeys((lo[i], lo[j], hi[j], hi[i])))  # axis → triangle
            if len(face) >= 3:
                faces.append(face)
    if not full:
        cap0 = tuple(dict.fromkeys(idx[k][0] for k in range(m)))
        cap1 = tuple(dict.fromkeys(idx[k][steps - 1] for k in reversed(range(m))))
        faces += [cap0, cap1]
    return _outward(verts, faces)


def sweep(path, profile, base_y: float = 0.0, closed: bool = False) -> Mesh:
    """Sweep a closed (d, h) moulding profile along an XZ path on the wall plane y = base_y.

    `d` points out of the wall (towards -Y); `h` follows the in-plane normal (-t_z, t_x).
    """
    verts: list[Vec3] = []
    rings: list[list[int]] = []
    n = len(path)
    for i, (x, z) in enumerate(path):
        a = path[i - 1] if (i > 0 or closed) else path[i]
        b = path[(i + 1) % n] if (i < n - 1 or closed) else path[i]
        tx, tz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, tz) or 1.0
        nx, nz = -tz / ln, tx / ln
        ring = []
        for d, h in profile:
            verts.append((x + nx * h, base_y - d, z + nz * h))
            ring.append(len(verts) - 1)
        rings.append(ring)
    faces = _skin(rings, closed)
    if not closed:
        faces += [tuple(reversed(rings[0])), tuple(rings[-1])]
    return _outward(verts, faces)


def _perpendicular(t) -> Vec3:
    ref = (0.0, 0.0, 1.0) if abs(t[2]) < 0.9 else (1.0, 0.0, 0.0)
    v = (
        t[1] * ref[2] - t[2] * ref[1],
        t[2] * ref[0] - t[0] * ref[2],
        t[0] * ref[1] - t[1] * ref[0],
    )
    ln = math.sqrt(sum(c * c for c in v))
    return (v[0] / ln, v[1] / ln, v[2] / ln)


def tube(points, radius: float, sides: int = 8) -> Mesh:
    """Round bar along a polyline (parallel-transported frame, capped ends)."""
    verts: list[Vec3] = []
    rings: list[list[int]] = []
    n = len(points)
    u_prev = None
    for i, p in enumerate(points):
        a, b = points[max(i - 1, 0)], points[min(i + 1, n - 1)]
        t = [b[k] - a[k] for k in range(3)]
        ln = math.sqrt(sum(c * c for c in t)) or 1.0
        t = [c / ln for c in t]
        if u_prev is None:
            u = _perpendicular(t)
        else:  # drop the tangent component of the previous normal: no twisting
            dot = sum(u_prev[k] * t[k] for k in range(3))
            u = [u_prev[k] - dot * t[k] for k in range(3)]
            lu = math.sqrt(sum(c * c for c in u)) or 1.0
            u = tuple(c / lu for c in u)
        v = (t[1] * u[2] - t[2] * u[1], t[2] * u[0] - t[0] * u[2], t[0] * u[1] - t[1] * u[0])
        ring = []
        for s in range(sides):
            ang = TAU * s / sides
            c, sn = math.cos(ang) * radius, math.sin(ang) * radius
            verts.append(tuple(p[k] + c * u[k] + sn * v[k] for k in range(3)))
            ring.append(len(verts) - 1)
        rings.append(ring)
        u_prev = u
    faces = _skin(rings, False) + [tuple(reversed(rings[0])), tuple(rings[-1])]
    return _outward(verts, faces)


def leaf(origin, up, out, side, length, width, curl, thickness: float = 0.012) -> Mesh:
    """Acanthus-like leaf: serrated, cupped, bulging out and curling at the tip; two-sided."""
    rows, cols = 14, 7
    top: list[Vec3] = []
    for i in range(rows + 1):
        s = i / rows
        w = width * (math.sin(math.pi * min(1.0, s * 1.1)) ** 0.6)
        w *= 1 + 0.18 * math.sin(10 * math.pi * s)  # serrated rim
        up_d = length * s - curl * max(0.0, s - 0.7) ** 2 * 8
        out_d = 0.25 * curl * s + curl * max(0.0, s - 0.6) * 2.2
        for j in range(cols + 1):
            v = -1 + 2 * j / cols
            cup = 0.25 * width * (1 - v * v)
            top.append(tuple(origin[k] + up[k] * up_d + out[k] * (out_d + cup) + side[k] * v * w
                             for k in range(3)))  # fmt: skip
    bottom = [tuple(p[k] - out[k] * thickness for k in range(3)) for p in top]
    nt = len(top)
    faces: list[tuple[int, ...]] = []
    for i in range(rows):
        for j in range(cols):
            a = i * (cols + 1) + j
            q = (a, a + 1, a + cols + 2, a + cols + 1)
            faces.append(q)
            faces.append(tuple(nt + x for x in reversed(q)))
    rim = ([j for j in range(cols + 1)]
           + [i * (cols + 1) + cols for i in range(1, rows + 1)]
           + [rows * (cols + 1) + j for j in range(cols - 1, -1, -1)]
           + [i * (cols + 1) for i in range(rows - 1, 0, -1)])  # fmt: skip
    directed = {(f[k], f[(k + 1) % 4]) for f in faces[::2] for k in range(4)}
    for p, q in zip(rim, rim[1:] + rim[:1], strict=True):
        if (p, q) in directed:
            faces.append((q, p, nt + p, nt + q))
        else:
            faces.append((p, q, nt + q, nt + p))
    return _outward(top + bottom, faces)


def spiral(center: Vec3, plane_u: Vec3, plane_v: Vec3, r0: float, r1: float, turns: float,
           start: float, steps: int = 80) -> list[Vec3]:  # fmt: skip
    """Points of a planar spiral shrinking linearly from r0 to r1 over `turns` turns."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        r = r0 + (r1 - r0) * t
        a = start + TAU * turns * t
        c, s = r * math.cos(a), r * math.sin(a)
        pts.append(tuple(center[k] + c * plane_u[k] + s * plane_v[k] for k in range(3)))
    return pts

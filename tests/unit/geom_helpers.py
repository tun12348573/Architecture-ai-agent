"""Test-only geometry helpers."""

RAY = (0.5773, 0.5774, 0.5775)  # skewed to avoid hitting edges exactly


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _ray_hits_triangle(origin, d, a, b, c) -> bool:
    e1, e2 = _sub(b, a), _sub(c, a)
    p = _cross(d, e2)
    det = _dot(e1, p)
    if abs(det) < 1e-12:
        return False
    inv = 1.0 / det
    s = _sub(origin, a)
    u = _dot(s, p) * inv
    if u < 0 or u > 1:
        return False
    q = _cross(s, e1)
    v = _dot(d, q) * inv
    if v < 0 or u + v > 1:
        return False
    return _dot(e2, q) * inv > 1e-12


def point_inside(mesh, point) -> bool:
    hits = 0
    for face in mesh.faces:
        verts = [mesh.vertices[i] for i in face]
        for k in range(1, len(verts) - 1):
            if _ray_hits_triangle(point, RAY, verts[0], verts[k], verts[k + 1]):
                hits += 1
    return hits % 2 == 1


def box_overlap_volume(a, b) -> float:
    vol = 1.0
    for axis in range(3):
        lo = max(a[0][axis], b[0][axis])
        hi = min(a[1][axis], b[1][axis])
        if hi <= lo:
            return 0.0
        vol *= hi - lo
    return vol

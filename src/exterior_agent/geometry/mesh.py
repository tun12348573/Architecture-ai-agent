"""Minimal polygon mesh value type (pure Python, no bpy)."""

from collections import Counter
from dataclasses import dataclass

Vec3 = tuple[float, float, float]
Bounds = tuple[Vec3, Vec3]


@dataclass(frozen=True)
class Mesh:
    vertices: list[Vec3]
    faces: list[tuple[int, ...]]

    def bounds(self) -> Bounds:
        xs, ys, zs = zip(*self.vertices, strict=True)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def is_closed(self) -> bool:
        edges: Counter[tuple[int, int]] = Counter()
        for face in self.faces:
            for a, b in zip(face, face[1:] + face[:1], strict=True):
                edges[(min(a, b), max(a, b))] += 1
        return bool(edges) and all(n == 2 for n in edges.values())


class MeshBuilder:
    """Accumulates quads with shared, deduplicated vertices and outward winding."""

    def __init__(self) -> None:
        self.vertices: list[Vec3] = []
        self.faces: list[tuple[int, ...]] = []
        self._index: dict[Vec3, int] = {}

    def vertex(self, v: Vec3) -> int:
        key = (round(v[0], 9) + 0.0, round(v[1], 9) + 0.0, round(v[2], 9) + 0.0)
        if key not in self._index:
            self._index[key] = len(self.vertices)
            self.vertices.append(key)
        return self._index[key]

    def quad(self, corners: list[Vec3], normal: Vec3) -> None:
        a, b, c = corners[0], corners[1], corners[2]
        e1 = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        e2 = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        n = (
            e1[1] * e2[2] - e1[2] * e2[1],
            e1[2] * e2[0] - e1[0] * e2[2],
            e1[0] * e2[1] - e1[1] * e2[0],
        )
        if n[0] * normal[0] + n[1] * normal[1] + n[2] * normal[2] < 0:
            corners = corners[::-1]
        self.faces.append(tuple(self.vertex(v) for v in corners))

    def build(self) -> Mesh:
        return Mesh(self.vertices, self.faces)


def box_mesh(lo: Vec3, hi: Vec3) -> Mesh:
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    mb = MeshBuilder()
    mb.quad([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0))
    mb.quad([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0))
    mb.quad([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0))
    mb.quad([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0))
    mb.quad([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1))
    mb.quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1))
    return mb.build()


def quad_mesh(lo: Vec3, hi: Vec3) -> Mesh:
    """Horizontal single-sided quad at lo.z facing +Z."""
    (x0, y0, z), (x1, y1, _) = lo, hi
    mb = MeshBuilder()
    mb.quad([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], (0, 0, 1))
    return mb.build()

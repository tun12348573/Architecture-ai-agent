"""Prism walls with polygon holes (arched/round openings) built without booleans."""

import math

import pytest

from exterior_agent.geometry.layout import WallFrame
from exterior_agent.geometry.polygon_wall import (
    arch_outline,
    circle_outline,
    prism_with_holes,
    rect_outline,
)
from tests.unit.geom_helpers import is_oriented, signed_volume

FRAME = WallFrame((0.0, 0.0, 0.0), (1, 0, 0), (0, 1, 0), 5.0, 0.0)  # front face at y = 0


def polygon_area(pts) -> float:
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1], strict=True))


def front_triangles(mesh):
    for f in mesh.faces:
        pts = [mesh.vertices[i] for i in f]
        if all(abs(p[1]) < 1e-9 for p in pts):
            yield [(p[0], p[2]) for p in pts]


def front_area(mesh) -> float:
    return sum(abs(polygon_area(t)) for t in front_triangles(mesh))


def inside(pt, poly) -> bool:
    x, y, hit = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def check_solid(mesh):
    assert mesh.is_closed() and is_oriented(mesh) and signed_volume(mesh) > 0


ARCHES = [arch_outline(0.5, 1.9, 0.6, 2.6), arch_outline(3.0, 4.2, 0.9, 2.7)]


def test_area_rect_minus_arches():
    mesh = prism_with_holes(rect_outline(0, 5, 0, 3.4), ARCHES, 0.2, FRAME)
    expected = 17.0 - sum(polygon_area(h) for h in ARCHES)
    assert front_area(mesh) == pytest.approx(expected, abs=1e-6)


def test_no_face_inside_hole():
    mesh = prism_with_holes(rect_outline(0, 5, 0, 3.4), ARCHES, 0.2, FRAME)
    for tri in front_triangles(mesh):
        c = (sum(p[0] for p in tri) / 3, sum(p[1] for p in tri) / 3)
        assert not any(inside(c, h) for h in ARCHES), c


def test_watertight():
    check_solid(prism_with_holes(rect_outline(0, 5, 0, 3.4), ARCHES, 0.2, FRAME))


def test_door_touching_sill():
    door = arch_outline(0.4, 2.2, 0.0, 3.0)
    mesh = prism_with_holes(rect_outline(0, 5, 0, 3.4), [door], 0.2, FRAME)
    check_solid(mesh)
    assert front_area(mesh) == pytest.approx(17.0 - polygon_area(door), abs=1e-6)


def test_close_holes():
    holes = [rect_outline(0.5, 1.5, 1, 2), rect_outline(1.6, 2.6, 1, 2)]
    mesh = prism_with_holes(rect_outline(0, 5, 0, 3.4), holes, 0.2, FRAME)
    check_solid(mesh)
    assert front_area(mesh) == pytest.approx(17.0 - 2.0, abs=1e-6)


def test_triangle_with_circle_hole():
    gable = [(0.0, 0.0), (5.0, 0.0), (2.5, 2.1)]
    oculus = circle_outline(2.5, 0.84, 0.45)
    mesh = prism_with_holes(gable, [oculus], 0.2, FRAME)
    check_solid(mesh)
    assert front_area(mesh) == pytest.approx(5.25 - polygon_area(oculus), abs=1e-6)


def test_outlines_counter_clockwise():
    assert polygon_area(arch_outline(0, 1, 0, 2)) > 0
    assert polygon_area(circle_outline(0, 0, 1)) == pytest.approx(math.pi, rel=0.01)


def test_deterministic():
    a = prism_with_holes(rect_outline(0, 5, 0, 3.4), ARCHES, 0.2, FRAME)
    b = prism_with_holes(rect_outline(0, 5, 0, 3.4), ARCHES, 0.2, FRAME)
    assert a == b

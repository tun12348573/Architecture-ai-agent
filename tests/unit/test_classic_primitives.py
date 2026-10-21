"""Ornament primitives for the neoclassical template: closed, deterministic, correctly sized."""

import math

import pytest

from exterior_agent.geometry.classic_primitives import lathe, leaf, spiral, sweep, tube
from tests.unit.geom_helpers import is_oriented, signed_volume

BALUSTER = [(0.0, 0.0), (0.06, 0.0), (0.06, 0.05), (0.04, 0.07), (0.035, 0.1), (0.05, 0.18),
            (0.075, 0.3), (0.07, 0.38), (0.045, 0.45), (0.025, 0.52), (0.03, 0.55), (0.055, 0.58),
            (0.055, 0.64), (0.0, 0.64)]  # fmt: skip
CORNICE = [(0, 0), (0.04, 0), (0.04, 0.05), (0.08, 0.07), (0.1, 0.12), (0.16, 0.15), (0.24, 0.17),
           (0.24, 0.24), (0.28, 0.26), (0.28, 0.32), (0, 0.32)]  # fmt: skip


def test_lathe_closed_and_bounds():
    mesh = lathe(BALUSTER, (1.0, 2.0, 3.0), segments=24)
    assert mesh.is_closed()
    lo, hi = mesh.bounds()
    assert hi[0] - 1.0 == pytest.approx(0.075, abs=1e-9)
    assert (lo[2], hi[2]) == pytest.approx((3.0, 3.64), abs=1e-9)


def test_lathe_partial_has_flat_ends():
    mesh = lathe([(0.0, 0.0), (1.0, 0.0), (1.0, 0.3), (0.0, 0.3)], (0.0, 0.0, 0.0),
                 segments=16, a0=math.pi, a1=2 * math.pi)  # fmt: skip
    assert mesh.is_closed()
    assert all(v[1] <= 1e-9 for v in mesh.vertices)


def test_sweep_straight_cornice_extent():
    mesh = sweep([(-1.0, 0.0), (1.0, 0.0)], CORNICE)
    assert mesh.is_closed()
    lo, hi = mesh.bounds()
    assert lo == pytest.approx((-1.0, -0.28, 0.0), abs=1e-9)
    assert hi == pytest.approx((1.0, 0.0, 0.32), abs=1e-9)


def test_sweep_arch_outward():
    r = 0.7
    path = [(r * math.cos(a), r * math.sin(a)) for a in (math.pi * (1 - k / 24) for k in range(25))]
    mesh = sweep(path, [(0, 0), (0.05, 0), (0.05, 0.2), (0, 0.2)])
    assert all(math.hypot(x, z) >= r - 1e-9 for x, _, z in mesh.vertices)


def test_tube_closed():
    mesh = tube([(0, 0, 0), (0, 0, 1), (0.5, 0, 1.5)], 0.02, sides=8)
    assert mesh.is_closed()


def test_leaf_closed_and_deterministic():
    args = ((0, 0, 0), (0, 0, 1), (0, -1, 0), (1, 0, 0), 0.3, 0.07, 0.05)
    a, b = leaf(*args), leaf(*args)
    assert a == b
    assert a.is_closed()
    lo, hi = a.bounds()
    assert hi[2] - lo[2] <= 0.3 + 1e-9


def test_spiral_radius_monotonic():
    pts = spiral((0, 0, 0), (1, 0, 0), (0, 0, 1), 0.3, 0.05, 1.5, 0.0)
    radii = [math.hypot(x, z) for x, _, z in pts]
    assert radii[0] == pytest.approx(0.3) and radii[-1] == pytest.approx(0.05)
    assert all(a >= b - 1e-12 for a, b in zip(radii, radii[1:], strict=False))


@pytest.mark.parametrize(
    "mesh",
    [
        lathe(BALUSTER, (0, 0, 0), segments=12),
        lathe(
            [(1.4, -0.12), (1.5, -0.1), (1.58, 0.0), (1.4, 0.0)],
            (0, 0, 0),
            12,
            math.pi,
            2 * math.pi,
        ),
        sweep([(-1.0, 0.0), (1.0, 0.0)], CORNICE),
        tube([(0, 0, 0), (0, 0, 1), (0.5, 0, 1.5)], 0.02),
        leaf((0, 0, 0), (0, 0, 1), (0, -1, 0), (1, 0, 0), 0.3, 0.07, 0.05),
    ],
)
def test_outward_consistent_winding(mesh):
    assert is_oriented(mesh) and signed_volume(mesh) > 0

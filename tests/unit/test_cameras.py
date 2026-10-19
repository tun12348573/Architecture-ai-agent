import itertools
import math

import pytest

from exterior_agent.domain.project import CANONICAL_CAMERA_IDS
from exterior_agent.domain.validate import parse_project
from exterior_agent.geometry.cameras import euler_xyz, fit_cameras, project_point
from exterior_agent.geometry.layout import building_bounds, site_bounds


@pytest.fixture
def demo(demo_data):
    return parse_project(demo_data)


@pytest.fixture
def cams(demo):
    return {c.id: c for c in fit_cameras(building_bounds(demo), site_bounds(demo))}


def corners(bounds):
    lo, hi = bounds
    return list(itertools.product(*zip(lo, hi, strict=True)))


def test_ten_unique_cameras(demo):
    poses = fit_cameras(building_bounds(demo), site_bounds(demo))
    assert [c.id for c in poses] == list(CANONICAL_CAMERA_IDS)
    for a, b in itertools.combinations(poses, 2):
        assert math.dist(a.location, b.location) > 0.5, (a.id, b.id)
        assert a.forward != pytest.approx(b.forward), (a.id, b.id)


def test_all_corners_in_frame_with_padding(demo, cams):
    for cam_id, cam in cams.items():
        target = site_bounds(demo) if cam_id in ("09_top", "10_aerial") else building_bounds(demo)
        extents = []
        for p in corners(target):
            x, y, depth = project_point(cam, p)
            assert depth > 0, cam_id
            extents.append(max(abs(x), abs(y)))
        assert max(extents) <= 0.8 + 1e-6, cam_id
        assert max(extents) >= 0.8 - 1e-3, cam_id


def test_orientation(cams):
    assert cams["01_front"].location[1] < 5.0
    assert cams["02_rear"].location[1] > 17.0
    assert cams["03_left"].location[0] < -2.25
    assert cams["04_right"].location[0] > 2.25
    left = cams["03_left"]
    assert project_point(left, (-2.25, 5, 0))[0] > project_point(left, (-2.25, 17, 0))[0]
    assert project_point(cams["01_front"], (-2.25, 5, 1.8))[0] < 0
    top = cams["09_top"]
    assert project_point(top, (0, 0, 0))[1] < project_point(top, (0, 18, 0))[1]
    assert top.projection == "ORTHO"
    for cam_id, cam in cams.items():
        if cam_id != "09_top":
            assert cam.projection == "PERSP", cam_id
        if cam_id not in ("09_top", "10_aerial"):
            assert cam.forward[2] == pytest.approx(0.0), cam_id
    aerial = cams["10_aerial"]
    assert aerial.forward[2] == pytest.approx(-math.sin(math.radians(35)))
    assert aerial.location[0] > 0 and aerial.location[1] < 9


def _rotation(euler):
    ax, ay, az = euler
    cx, sx, cy, sy, cz, sz = (
        math.cos(ax),
        math.sin(ax),
        math.cos(ay),
        math.sin(ay),
        math.cos(az),
        math.sin(az),
    )
    rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    return mul(rz, mul(ry, rx))  # Blender XYZ Euler


def test_euler_reproduces_forward(cams):
    for cam_id, cam in cams.items():
        r = _rotation(euler_xyz(cam))

        def apply(v, r=r):
            return tuple(sum(r[i][k] * v[k] for k in range(3)) for i in range(3))

        assert apply((0, 0, -1)) == pytest.approx(cam.forward, abs=1e-6), cam_id
        assert apply((0, 1, 0)) == pytest.approx(cam.up, abs=1e-6), cam_id

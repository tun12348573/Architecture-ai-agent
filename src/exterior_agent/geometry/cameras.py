"""Canonical camera set fitted to building/site bounds (pure Python)."""

import itertools
import math
from dataclasses import dataclass
from typing import Literal

from exterior_agent.domain.project import CANONICAL_CAMERA_IDS
from exterior_agent.geometry.mesh import Bounds, Vec3

PADDING = 0.10
NDC_LIMIT = 1.0 - 2 * PADDING  # 10% of the frame kept free on each side
LENS_MM = 35.0
SENSOR_MM = 36.0
ASPECT = 16 / 9
AERIAL_ELEVATION_DEG = 35.0
TOP_CAMERA_HEIGHT = 50.0
_DIAG = 1 / math.sqrt(2)

# Horizontal viewing directions: the camera looks along these from outside the building.
_HORIZONTAL_FORWARD: dict[str, Vec3] = {
    "01_front": (0.0, 1.0, 0.0),
    "02_rear": (0.0, -1.0, 0.0),
    "03_left": (1.0, 0.0, 0.0),
    "04_right": (-1.0, 0.0, 0.0),
    "05_front_left": (_DIAG, _DIAG, 0.0),
    "06_front_right": (-_DIAG, _DIAG, 0.0),
    "07_rear_left": (_DIAG, -_DIAG, 0.0),
    "08_rear_right": (-_DIAG, -_DIAG, 0.0),
}


@dataclass(frozen=True)
class CameraPose:
    id: str
    location: Vec3
    forward: Vec3
    up: Vec3
    projection: Literal["PERSP", "ORTHO"]
    lens_mm: float
    sensor_mm: float
    ortho_scale: float | None


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def _basis(forward: Vec3, up_hint: Vec3) -> tuple[Vec3, Vec3]:
    right = _norm(_cross(forward, up_hint))
    return right, _cross(right, forward)


def _centre(bounds: Bounds) -> Vec3:
    lo, hi = bounds
    return ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)


def _corners(bounds: Bounds) -> list[Vec3]:
    lo, hi = bounds
    return list(itertools.product(*zip(lo, hi, strict=True)))


def _fit_perspective(cam_id: str, target: Bounds, forward: Vec3) -> CameraPose:
    """Smallest distance along -forward that keeps every target corner inside NDC_LIMIT."""
    right, up = _basis(forward, (0.0, 0.0, 1.0))
    c = _centre(target)
    tan_h = (SENSOR_MM / 2) / LENS_MM
    tan_v = tan_h / ASPECT
    d = 0.0
    for p in _corners(target):
        q = (p[0] - c[0], p[1] - c[1], p[2] - c[2])
        x, y, z = _dot(q, right), _dot(q, up), _dot(q, forward)
        d = max(d, abs(x) / (NDC_LIMIT * tan_h) - z, abs(y) / (NDC_LIMIT * tan_v) - z)
    location = (c[0] - d * forward[0], c[1] - d * forward[1], c[2] - d * forward[2])
    return CameraPose(cam_id, location, forward, up, "PERSP", LENS_MM, SENSOR_MM, None)


def _fit_top(target: Bounds) -> CameraPose:
    lo, hi = target
    cx, cy, _ = _centre(target)
    width, depth = hi[0] - lo[0], hi[1] - lo[1]
    scale = max(width, depth * ASPECT) / NDC_LIMIT
    # Looking down with +Y up in the image puts the front (-Y) at the bottom.
    return CameraPose(
        "09_top",
        (cx, cy, hi[2] + TOP_CAMERA_HEIGHT),
        (0.0, 0.0, -1.0),
        (0.0, 1.0, 0.0),
        "ORTHO",
        LENS_MM,
        SENSOR_MM,
        scale,
    )


def fit_cameras(building: Bounds, site: Bounds) -> list[CameraPose]:
    whole = (
        tuple(min(a, b) for a, b in zip(building[0], site[0], strict=True)),
        tuple(max(a, b) for a, b in zip(building[1], site[1], strict=True)),
    )
    elev = math.radians(AERIAL_ELEVATION_DEG)
    aerial_forward = (-_DIAG * math.cos(elev), _DIAG * math.cos(elev), -math.sin(elev))
    poses = {cid: _fit_perspective(cid, building, f) for cid, f in _HORIZONTAL_FORWARD.items()}
    poses["09_top"] = _fit_top(whole)
    poses["10_aerial"] = _fit_perspective("10_aerial", whole, aerial_forward)
    return [poses[cid] for cid in CANONICAL_CAMERA_IDS]


def project_point(pose: CameraPose, p: Vec3, aspect: float = ASPECT) -> tuple[float, float, float]:
    """(x_ndc, y_ndc, depth); the point is in frame when |x|, |y| <= 1 and depth > 0."""
    right = _cross(pose.forward, pose.up)
    q = (p[0] - pose.location[0], p[1] - pose.location[1], p[2] - pose.location[2])
    x, y, depth = _dot(q, right), _dot(q, pose.up), _dot(q, pose.forward)
    if pose.projection == "ORTHO":
        half_w = pose.ortho_scale / 2
        return x / half_w, y / (half_w / aspect), depth
    tan_h = (pose.sensor_mm / 2) / pose.lens_mm
    return x / (depth * tan_h), y / (depth * tan_h / aspect), depth


def euler_xyz(pose: CameraPose) -> Vec3:
    """Blender XYZ Euler for a camera (looks along local -Z with local +Y up)."""
    right = _cross(pose.forward, pose.up)
    back = (-pose.forward[0], -pose.forward[1], -pose.forward[2])
    # Rotation matrix columns are the camera's local X, Y, Z axes in world space.
    m = [[right[i], pose.up[i], back[i]] for i in range(3)]
    ry = math.asin(max(-1.0, min(1.0, -m[2][0])))
    rx = math.atan2(m[2][1], m[2][2])
    rz = math.atan2(m[1][0], m[0][0])
    return (rx, ry, rz)

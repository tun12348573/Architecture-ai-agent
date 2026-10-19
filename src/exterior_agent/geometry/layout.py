"""Placement of site and building in world space (metres, Z-up, front = -Y)."""

from dataclasses import dataclass

from exterior_agent.domain.project import Project
from exterior_agent.geometry.mesh import Bounds, Vec3


def footprint_bounds(p: Project) -> Bounds:
    b = p.building
    half = b.footprint_width.value / 2
    y0 = p.site.front_setback.value
    return (-half, y0, 0.0), (half, y0 + b.footprint_depth.value, b.wall_height.value)


def building_bounds(p: Project) -> Bounds:
    lo, hi = footprint_bounds(p)
    return lo, (hi[0], hi[1], hi[2] + p.building.roof.thickness.value)


def site_bounds(p: Project) -> Bounds:
    half = p.site.width.value / 2
    top = building_bounds(p)[1][2]
    return (-half, 0.0, 0.0), (half, p.site.depth.value, top)


@dataclass(frozen=True)
class WallFrame:
    """Local wall frame: u runs along the facade from its left end as seen from outside,
    v points inward through the wall thickness, z is up."""

    origin: Vec3
    u_axis: Vec3
    v_axis: Vec3
    length: float  # local length of the wall solid
    u_shift: float  # subtract from a facade offset to get local u

    def to_world(self, u: float, v: float, z: float) -> Vec3:
        o, a, b = self.origin, self.u_axis, self.v_axis
        return (o[0] + u * a[0] + v * b[0], o[1] + u * a[1] + v * b[1], o[2] + z)


def wall_frames(p: Project) -> dict[str, WallFrame]:
    """Front/rear walls span the full width; side walls fit between them."""
    (x0, y0, _), (x1, y1, _) = footprint_bounds(p)
    t = p.building.wall_thickness.value
    width, depth = x1 - x0, y1 - y0
    return {
        "front": WallFrame((x0, y0, 0.0), (1, 0, 0), (0, 1, 0), width, 0.0),
        "rear": WallFrame((x1, y1, 0.0), (-1, 0, 0), (0, -1, 0), width, 0.0),
        "left": WallFrame((x0, y1 - t, 0.0), (0, -1, 0), (1, 0, 0), depth - 2 * t, t),
        "right": WallFrame((x1, y0 + t, 0.0), (0, 1, 0), (-1, 0, 0), depth - 2 * t, t),
    }

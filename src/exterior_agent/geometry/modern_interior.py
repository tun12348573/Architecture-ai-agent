"""Dark matte panels behind glazed openings: clear glass must not show sky through the house.

Only for projects whose glass transmits (transmission > 0); older projects keep their plan.
"""

from exterior_agent.geometry.context import quad_wall
from exterior_agent.geometry.mesh import Mesh
from exterior_agent.geometry.modern_massing import PlanObject, floor_base_z, floor_front_y

GLAZED = {"modern_townhouse": ("window", "door_4leaf"),
          "neoclassical_townhouse": ("window", "door", "door_wood")}  # fmt: skip
BACKDROP_DEPTH = 1.5  # metres behind the inner wall face
BACKDROP_MARGIN = 0.6  # beyond each opening edge, clipped to the room
INTERIOR_MATERIAL = {"name": "MAT_Interior", "base_color": [0.04, 0.035, 0.03],
                     "roughness": 0.9, "alpha": 1.0}  # fmt: skip


def backdrop_objects(p) -> list[PlanObject]:
    m, glazed = p.body, GLAZED[p.template]
    if p.materials.window_glass.value.transmission <= 0:
        return []
    t, half = m.wall_thickness.value, m.footprint_width.value / 2
    yr = p.site.front_setback.value + m.footprint_depth.value
    out = []
    for n, f in enumerate(m.floors, start=1):
        z_floor = floor_base_z(m, n)
        z_top = z_floor + f.height.value - m.slab_thickness.value
        y_in0, y_in1 = floor_front_y(p, n) + t, yr - t
        depth = min(BACKDROP_DEPTH, (y_in1 - y_in0) / 3)
        for side, y, flip in (("front", y_in0 + depth, False), ("rear", y_in1 - depth, True)):
            for o in getattr(f, f"openings_{side}"):
                if o.kind not in glazed:
                    continue
                # facade offsets run left→right seen from outside: the rear wall is mirrored
                a = -half + o.offset.value
                x0, x1 = (a, a + o.width.value) if not flip else (-a - o.width.value, -a)
                x0, x1 = max(-half + t, x0 - BACKDROP_MARGIN), min(half - t, x1 + BACKDROP_MARGIN)
                z0 = max(z_floor, z_floor + o.sill.value - BACKDROP_MARGIN)
                z1 = min(z_top, z_floor + o.sill.value + o.height.value + BACKDROP_MARGIN)
                quad = quad_wall(x0, x1, y, z0, z1)
                if flip:  # face the rear opening (+Y)
                    quad = Mesh(quad.vertices, [tuple(reversed(quad.faces[0]))])
                out.append(
                    PlanObject(f"Backdrop_{o.id}", "Interior_Backdrop", quad, "MAT_Interior")
                )
    return out

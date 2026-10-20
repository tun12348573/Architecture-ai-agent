"""Ground-floor front cladding: a thin brick skin on the facade, cut by the wall's openings."""

from exterior_agent.domain.modern_rules import cladding_top
from exterior_agent.geometry.layout import WallFrame
from exterior_agent.geometry.mesh import Mesh
from exterior_agent.geometry.modern_massing import PlanObject, floor_front_y
from exterior_agent.geometry.walls import wall_mesh


def cladding_objects(p) -> list[PlanObject]:
    m = p.modern
    if m.cladding is None:
        return []
    w, th = m.footprint_width.value, m.cladding.thickness.value
    # Same u as the floor-1 front wall (u_shift 0), shifted outward by the skin thickness.
    frame = WallFrame((-w / 2, floor_front_y(p, 1) - th, 0.0), (1, 0, 0), (0, 1, 0), w, 0.0)
    holes = [
        (
            o.offset.value,
            o.offset.value + o.width.value,
            o.sill.value,
            o.sill.value + o.height.value,
        )
        for o in m.floors[0].openings_front
    ]
    local = wall_mesh(w, cladding_top(m), th, holes)
    mesh = Mesh([frame.to_world(*v) for v in local.vertices], local.faces)
    return [PlanObject("Cladding_F1_Front", "Facade", mesh, "MAT_Cladding")]

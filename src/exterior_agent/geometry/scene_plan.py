"""Fully resolved, JSON-serializable scene description consumed by the Blender build script."""

import math

from exterior_agent.domain.project import Project
from exterior_agent.domain.render import RenderSettings
from exterior_agent.geometry.cameras import euler_xyz, fit_cameras
from exterior_agent.geometry.layout import building_bounds, site_bounds
from exterior_agent.geometry.mesh import Mesh
from exterior_agent.geometry.walls import (
    build_walls,
    door_window_meshes,
    opening_boxes,
    roof_mesh,
    site_meshes,
)

SCHEMA = "scene_plan/1"
MATERIAL_NAMES = {
    "wall": "MAT_Wall",
    "roof": "MAT_Roof",
    "door": "MAT_Door",
    "window_glass": "MAT_Window_Glass",
    "land": "MAT_Land",
    "context_ground": "MAT_Context_Ground",
}
SUN_ROTATION = (math.radians(50), 0.0, math.radians(35))  # light from the front-right, above
SUN_STRENGTH = 3.0
WORLD_COLOR = [0.60, 0.72, 0.88]
CAMERA_CLIP_END = 1000.0


def _mesh(name: str, collection: str, mesh: Mesh, material_key: str) -> dict:
    return {
        "name": name,
        "collection": collection,
        "type": "MESH",
        "vertices": [list(v) for v in mesh.vertices],
        "faces": [list(f) for f in mesh.faces],
        "material": MATERIAL_NAMES[material_key],
    }


def build_scene_plan(project: Project, render: RenderSettings) -> dict:
    objects = [_mesh(n, "Building", m, "wall") for n, m in build_walls(project).items()]
    objects.append(_mesh("Roof_Slab", "Building", roof_mesh(project), "roof"))
    for opening_id, (lo, hi) in opening_boxes(project).items():
        objects.append(
            {
                "name": f"Opening_{opening_id}",
                "collection": "Openings",
                "type": "EMPTY",
                "location": [(a + b) / 2 for a, b in zip(lo, hi, strict=True)],
                "scale": [(b - a) / 2 for a, b in zip(lo, hi, strict=True)],
            }
        )
    for name, mesh in door_window_meshes(project).items():
        is_door = name.startswith("Door_")
        objects.append(
            _mesh(
                name, "Doors" if is_door else "Windows", mesh, "door" if is_door else "window_glass"
            )
        )
    sites = site_meshes(project)
    objects.append(_mesh("Site_Land", "Site", sites["Site_Land"], "land"))
    objects.append(_mesh("Site_Context", "Site", sites["Site_Context"], "context_ground"))

    materials = []
    for key, name in MATERIAL_NAMES.items():
        spec = getattr(project.materials, key).value
        materials.append(
            {
                "name": name,
                "base_color": list(spec.base_color),
                "roughness": spec.roughness,
                "alpha": spec.alpha,
            }
        )

    cameras = [
        {
            "name": f"CAM_{pose.id}",
            "id": pose.id,
            "location": list(pose.location),
            "rotation_euler": list(euler_xyz(pose)),
            "projection": pose.projection,
            "lens_mm": pose.lens_mm,
            "sensor_mm": pose.sensor_mm,
            "ortho_scale": pose.ortho_scale,
            "clip_end": CAMERA_CLIP_END,
        }
        for pose in fit_cameras(building_bounds(project), site_bounds(project))
    ]
    return {
        "schema": SCHEMA,
        "project_id": project.project_id,
        "project_revision": project.project_revision,
        "objects": objects,
        "materials": materials,
        "cameras": cameras,
        "sun": {"rotation_euler": list(SUN_ROTATION), "strength": SUN_STRENGTH},
        "world_color": WORLD_COLOR,
        "render": render.to_dict(),
    }


def required_object_names(plan: dict) -> set[str]:
    return {o["name"] for o in plan["objects"]}


def required_material_names(plan: dict) -> set[str]:
    return {m["name"] for m in plan["materials"]}

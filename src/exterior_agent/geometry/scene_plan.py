"""Fully resolved, JSON-serializable scene description consumed by the Blender build script."""

import math

from exterior_agent.domain.project import Project
from exterior_agent.domain.render import RenderSettings
from exterior_agent.geometry.cameras import euler_xyz, fit_cameras
from exterior_agent.geometry.layout import building_bounds, site_bounds
from exterior_agent.geometry.mesh import Bounds, Mesh
from exterior_agent.geometry.modern_facade import facade_objects
from exterior_agent.geometry.modern_massing import massing_objects
from exterior_agent.geometry.modern_site import site_objects
from exterior_agent.geometry.primitives import box_uvs
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
# modern_townhouse: material name -> role in project.materials
MODERN_MATERIALS = {
    "MAT_Wall": "wall",
    "MAT_Roof": "roof",
    "MAT_Door": "door",
    "MAT_Glass": "window_glass",
    "MAT_Frame": "frame",
    "MAT_Aluminium": "aluminium",
    "MAT_Louver": "louver",
    "MAT_Terrace_Floor": "terrace_floor",
    "MAT_Paving": "paving",
    "MAT_Grass": "grass",
    "MAT_Soil": "soil",
    "MAT_Pergola_Wood": "pergola_wood",
    "MAT_Context_Ground": "context_ground",
    "MAT_Props": "props",
}
BUILDING_COLLECTIONS = {"Building", "Doors", "Windows", "Balconies", "Facade", "Roof"}


def _mesh(name: str, collection: str, mesh: Mesh, material_key: str) -> dict:
    return {
        "name": name,
        "collection": collection,
        "type": "MESH",
        "vertices": [list(v) for v in mesh.vertices],
        "faces": [list(f) for f in mesh.faces],
        "material": MATERIAL_NAMES[material_key],
    }


def _empty(name: str, lo, hi) -> dict:
    return {
        "name": name,
        "collection": "Openings",
        "type": "EMPTY",
        "location": [(a + b) / 2 for a, b in zip(lo, hi, strict=True)],
        "scale": [(b - a) / 2 for a, b in zip(lo, hi, strict=True)],
    }


def _material(name: str, spec) -> dict:
    return {
        "name": name,
        "base_color": list(spec.base_color),
        "roughness": spec.roughness,
        "alpha": spec.alpha,
    }


def _basic_objects_and_materials(project: Project) -> tuple[list[dict], list[dict]]:
    objects = [_mesh(n, "Building", m, "wall") for n, m in build_walls(project).items()]
    objects.append(_mesh("Roof_Slab", "Building", roof_mesh(project), "roof"))
    for opening_id, (lo, hi) in opening_boxes(project).items():
        objects.append(_empty(f"Opening_{opening_id}", lo, hi))
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

    materials = [
        _material(name, getattr(project.materials, key).value)
        for key, name in MATERIAL_NAMES.items()
    ]
    return objects, materials


def _modern_plan_objects(project: Project):
    return massing_objects(project) + facade_objects(project) + site_objects(project)


def _union(boxes: list[Bounds]) -> Bounds:
    return (
        tuple(min(b[0][k] for b in boxes) for k in range(3)),
        tuple(max(b[1][k] for b in boxes) for k in range(3)),
    )


def modern_bounds(project: Project) -> tuple[Bounds, Bounds]:
    """(building, site) bounds used to fit the cameras of a modern_townhouse project."""
    building = _union(
        [
            o.mesh.bounds()
            for o in _modern_plan_objects(project)
            if o.mesh is not None and o.collection in BUILDING_COLLECTIONS
        ]
    )
    s = project.site
    lot = ((-s.width.value / 2, 0.0, 0.0), (s.width.value / 2, s.depth.value, building[1][2]))
    return building, _union([building, lot])


def _modern_objects_and_materials(project: Project) -> tuple[list[dict], list[dict]]:
    objects = []
    for o in _modern_plan_objects(project):
        if o.mesh is None:
            objects.append(_empty(o.name, *o.empty_box))
            continue
        objects.append(
            {
                "name": o.name,
                "collection": o.collection,
                "type": "MESH",
                "vertices": [list(v) for v in o.mesh.vertices],
                "faces": [list(f) for f in o.mesh.faces],
                "material": o.material,
                "uvs": [[list(uv) for uv in face] for face in box_uvs(o.mesh)],
            }
        )
    used = {o["material"] for o in objects if o["type"] == "MESH"}
    materials = [
        _material(name, getattr(project.materials, role).value)
        for name, role in MODERN_MATERIALS.items()
        if name in used
    ]
    return objects, materials


def build_scene_plan(project: Project, render: RenderSettings) -> dict:
    if project.template == "modern_townhouse":
        objects, materials = _modern_objects_and_materials(project)
        building, site = modern_bounds(project)
    else:
        objects, materials = _basic_objects_and_materials(project)
        building, site = building_bounds(project), site_bounds(project)
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
        for pose in fit_cameras(building, site)
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

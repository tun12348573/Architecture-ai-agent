"""Fully resolved, JSON-serializable scene description consumed by the Blender build script."""

import math

from exterior_agent.assets.catalog import load_catalog
from exterior_agent.domain.project import Project
from exterior_agent.domain.render import RenderSettings
from exterior_agent.geometry.cameras import euler_xyz, fit_cameras
from exterior_agent.geometry.classic_facade import classic_facade_objects
from exterior_agent.geometry.classic_massing import classic_massing_objects
from exterior_agent.geometry.context import NEIGHBOUR_TINTS, context_objects
from exterior_agent.geometry.context_assets import (
    PLANT_TURN,
    AssetPlacement,
    context_asset_specs,
)
from exterior_agent.geometry.layout import building_bounds, site_bounds
from exterior_agent.geometry.mesh import Bounds, Mesh
from exterior_agent.geometry.modern_cladding import cladding_objects
from exterior_agent.geometry.modern_facade import facade_objects
from exterior_agent.geometry.modern_interior import INTERIOR_MATERIAL, backdrop_objects
from exterior_agent.geometry.modern_massing import massing_objects, roof_plant_positions
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
SUN_STRENGTH_WITH_HDRI = 1.0  # the HDRI already lights the scene and contains the sun
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
    "MAT_Cladding": "cladding",
    "MAT_Asphalt": "asphalt",
    "MAT_Sidewalk": "sidewalk",
    "MAT_Kerb": "kerb",
    "MAT_Road_Marking": "road_marking",
    "MAT_Neighbour_Glass": "neighbour_glass",
    # neoclassical_townhouse roles (M2d)
    "MAT_Trim": "trim",
    "MAT_Panel": "panel",
    "MAT_Roof_Tiles": "roof_tiles",
    "MAT_Iron": "iron",
    "MAT_Door_Wood": "door_wood",
}
ROOF_PLANT_HEIGHT = 1.2  # shrubs in the roof planter stay below the pergola
NEIGHBOUR_PREFIX = "MAT_Neighbour_"  # + tint number: neighbour_wall tinted per house
BUILDING_COLLECTIONS = {"Building", "Doors", "Windows", "Balconies", "Facade", "Roof", "Bay"}
TOWNHOUSES = ("modern_townhouse", "neoclassical_townhouse")


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
    out = {
        "name": name,
        "base_color": list(spec.base_color),
        "roughness": spec.roughness,
        "alpha": spec.alpha,
    }
    if spec.transmission > 0:  # only when set: plans of older projects stay byte-identical
        out["transmission"] = spec.transmission
    if spec.metallic > 0:
        out["metallic"] = spec.metallic
    return out


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
    """Building + site objects of a townhouse template (camera bounds and lot checks use these)."""
    if project.template == "neoclassical_townhouse":
        return (
            classic_massing_objects(project)
            + classic_facade_objects(project)
            + site_objects(project)
        )
    return (
        massing_objects(project)
        + facade_objects(project)
        + cladding_objects(project)
        + site_objects(project)
    )


def _union(boxes: list[Bounds]) -> Bounds:
    return (
        tuple(min(b[0][k] for b in boxes) for k in range(3)),
        tuple(max(b[1][k] for b in boxes) for k in range(3)),
    )


def template_bounds(project: Project) -> tuple[Bounds, Bounds]:
    """(building, site) bounds used to fit the cameras of a townhouse project."""
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


modern_bounds = template_bounds  # name used before the neoclassical template


TEXTURE_ROLES = ("base_color", "roughness", "normal")


def _asset_ref(asset, f) -> dict:
    return {"path": f"materials/{asset.id}/{f.path}", "sha256": f.sha256}


def _textures(spec, catalog) -> dict:
    asset = catalog.get(spec.texture)
    return {
        "textures": {
            f.role: _asset_ref(asset, f)
            for f in asset.files
            if f.role in TEXTURE_ROLES and (spec.texture_color or f.role != "base_color")
        },
        "texture_scale_m": asset.scale_m or 1.0,
    }


def _world_and_plants(project: Project, catalog) -> dict:
    extra: dict = {}
    if project.world is not None:
        w = project.world
        hdri = catalog.get(w.hdri.value)
        extra["world"] = {
            "hdri": _asset_ref(hdri, hdri.files[0]),
            "strength": w.strength.value,
            "rotation_deg": w.rotation_deg.value,
        }
    garden = getattr(project.body.roof, "garden", None)
    roof_models = [m.value for m in (garden.plant_models if garden else [])]
    placements = [
        AssetPlacement(
            f"Plant_Roof_{i + 1}", "Roof", roof_models[i % len(roof_models)], location,
            round(i * PLANT_TURN, 6), 1.0, garden.planter_width.value + 0.2, ROOF_PLANT_HEIGHT,
        )
        for i, location in enumerate(roof_plant_positions(project) if roof_models else [])
    ] + context_asset_specs(project)  # fmt: skip
    if placements:
        extra["assets"] = [_asset_entry(a, catalog.get(a.model)) for a in placements]
    return extra


def _asset_entry(a: AssetPlacement, model) -> dict:
    main = next(f for f in model.files if f.role == "gltf")
    fit = (
        {}
        if a.fit_diameter is None
        else {"fit": {"diameter": a.fit_diameter, "height": a.fit_height}}
    )
    return {
        **fit,
        "name": a.name,
        "collection": a.collection,
        "model": _asset_ref(model, main),
        "includes": [_asset_ref(model, f) for f in model.files if f.role == "include"],
        "location": list(a.location),
        "rotation_z": a.rotation_z,
        "scale": a.scale,
    }


def _modern_objects_and_materials(
    project: Project, textured: bool = False
) -> tuple[list[dict], list[dict]]:
    objects = []
    extra_objects = context_objects(project)
    if project.template == "modern_townhouse":  # classic massing already places its backdrops
        extra_objects += backdrop_objects(project)
    for o in _modern_plan_objects(project) + extra_objects:
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
                "uvs": [[list(uv) for uv in face] for face in (o.uvs or box_uvs(o.mesh))],
            }
        )
    used = {o["material"] for o in objects if o["type"] == "MESH"}
    catalog = load_catalog() if textured else None
    materials = []
    for name, role in MODERN_MATERIALS.items():
        if name not in used:
            continue
        spec = getattr(project.materials, role).value
        entry = _material(name, spec)
        if textured and spec.texture is not None:
            entry.update(_textures(spec, catalog))
        materials.append(entry)
    if INTERIOR_MATERIAL["name"] in used:
        materials.append(dict(INTERIOR_MATERIAL))
    for name in sorted(n for n in used if n.startswith(NEIGHBOUR_PREFIX) and n[-1].isdigit()):
        spec = project.materials.neighbour_wall.value
        entry = _material(name, spec)
        tint = NEIGHBOUR_TINTS[int(name.removeprefix(NEIGHBOUR_PREFIX)) - 1]
        entry["base_color"] = [round(a * b, 6) for a, b in zip(spec.base_color, tint, strict=True)]
        if textured and spec.texture is not None:
            entry.update(_textures(spec, catalog))
        materials.append(entry)
    return objects, materials


def build_scene_plan(project: Project, render: RenderSettings) -> dict:
    extra: dict = {}
    if project.template in TOWNHOUSES:
        textured = render.profile != "smoke"  # smoke stays flat and asset-free
        objects, materials = _modern_objects_and_materials(project, textured)
        building, site = template_bounds(project)
        if textured:
            extra = _world_and_plants(project, load_catalog())
    else:
        objects, materials = _basic_objects_and_materials(project)
        building, site = building_bounds(project), site_bounds(project)
    sun = SUN_STRENGTH_WITH_HDRI if "world" in extra else SUN_STRENGTH
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
        "sun": {"rotation_euler": list(SUN_ROTATION), "strength": sun},
        "world_color": WORLD_COLOR,
        "render": render.to_dict(),
        **extra,
    }


def required_object_names(plan: dict) -> set[str]:
    return {o["name"] for o in plan["objects"]}


def required_material_names(plan: dict) -> set[str]:
    return {m["name"] for m in plan["materials"]}


def required_asset_files(plan: dict) -> list[tuple[str, str, str]]:
    """(asset_id, file path inside the asset, sha256) for every asset file the plan uses."""
    refs = [t for m in plan["materials"] for t in m.get("textures", {}).values()]
    if "world" in plan:
        refs.append(plan["world"]["hdri"])
    for a in plan.get("assets", []):
        refs += [a["model"], *a["includes"]]
    out: list[tuple[str, str, str]] = []
    for ref in refs:
        _, asset_id, rel = ref["path"].split("/", 2)
        key = (asset_id, rel, ref["sha256"])
        if key not in out:
            out.append(key)
    return out

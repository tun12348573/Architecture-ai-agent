"""Runs inside Blender: build the canonical scene from scene_plan.json, save .blend, export GLB.

Usage (fixed by exterior_agent.blender.invoke):
  blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
    --python build_scene.py -- --plan scene_plan.json --blend model.blend --glb model.glb
Only stdlib + bpy: Blender's embedded Python has no project dependencies.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="build_scene.py")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--glb", required=True)
    return parser.parse_args(argv)


def clear_scene() -> None:
    for collection in (
        bpy.data.objects,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.collections,
    ):
        for block in list(collection):
            collection.remove(block)


def _socket(sockets, identifier: str):
    return next(s for s in sockets if s.identifier == identifier)


def _image_node(tree, path: Path, non_color: bool, scale_m: float):
    image = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        image.colorspace_settings.name = "Non-Color"
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    uv = tree.nodes.new("ShaderNodeUVMap")
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1 / scale_m, 1 / scale_m, 1.0)  # UVs are metres
    tree.links.new(uv.outputs["UV"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
    return node


def add_textures(mat, spec: dict, base: Path) -> None:
    """PBR maps from the revision's materials/; base colour tinted only when not white."""
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    tex, scale = spec["textures"], spec.get("texture_scale_m", 1.0)
    if "base_color" in tex:
        color = _image_node(tree, base / tex["base_color"]["path"], False, scale)
        if tuple(spec["base_color"]) == (1.0, 1.0, 1.0):
            tree.links.new(color.outputs["Color"], bsdf.inputs["Base Color"])
        else:
            mix = tree.nodes.new("ShaderNodeMix")
            mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
            mix.inputs[0].default_value = 1.0
            tree.links.new(color.outputs["Color"], _socket(mix.inputs, "A_Color"))
            _socket(mix.inputs, "B_Color").default_value = (*spec["base_color"], 1.0)
            tree.links.new(_socket(mix.outputs, "Result_Color"), bsdf.inputs["Base Color"])
    if "roughness" in tex:
        rough = _image_node(tree, base / tex["roughness"]["path"], True, scale)
        tree.links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
    if "normal" in tex:
        normal = _image_node(tree, base / tex["normal"]["path"], True, scale)
        normal_map = tree.nodes.new("ShaderNodeNormalMap")
        tree.links.new(normal.outputs["Color"], normal_map.inputs["Color"])
        tree.links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])


def make_material(spec: dict, base: Path) -> bpy.types.Material:
    mat = bpy.data.materials.new(spec["name"])
    if mat.node_tree is None:  # older API: nodes are opt-in
        mat.use_nodes = True
    rgba = (*spec["base_color"], 1.0)
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = spec["roughness"]
    mat.diffuse_color = (*spec["base_color"], spec["alpha"])
    if spec["alpha"] < 1.0:
        bsdf.inputs["Alpha"].default_value = spec["alpha"]
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
    if "textures" in spec:
        add_textures(mat, spec, base)
    return mat


def get_collection(name: str, scene: bpy.types.Scene) -> bpy.types.Collection:
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        scene.collection.children.link(coll)
    return coll


def add_object(spec: dict, scene, materials: dict) -> None:
    coll = get_collection(spec["collection"], scene)
    if spec["type"] == "MESH":
        mesh = bpy.data.meshes.new(spec["name"])
        mesh.from_pydata(
            [tuple(v) for v in spec["vertices"]], [], [tuple(f) for f in spec["faces"]]
        )
        if "uvs" in spec:  # per face, per corner; loops follow the face order of from_pydata
            layer = mesh.uv_layers.new(name="UVMap")
            flat = [c for face in spec["uvs"] for uv in face for c in uv]
            layer.data.foreach_set("uv", flat)
        mesh.validate()
        mesh.update()
        mesh.materials.append(materials[spec["material"]])
        obj = bpy.data.objects.new(spec["name"], mesh)
    else:
        obj = bpy.data.objects.new(spec["name"], None)
        obj.empty_display_type = "CUBE"
        obj.empty_display_size = 1.0
        obj.location = spec["location"]
        obj.scale = spec["scale"]
    coll.objects.link(obj)


def add_camera(spec: dict, scene) -> bpy.types.Object:
    cam = bpy.data.cameras.new(spec["name"])
    cam.type = spec["projection"]
    cam.lens = spec["lens_mm"]
    cam.sensor_width = spec["sensor_mm"]
    cam.sensor_fit = "HORIZONTAL"
    cam.clip_end = spec["clip_end"]
    if spec["ortho_scale"] is not None:
        cam.ortho_scale = spec["ortho_scale"]
    obj = bpy.data.objects.new(spec["name"], cam)
    obj.location = spec["location"]
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = spec["rotation_euler"]
    get_collection("Cameras", scene).objects.link(obj)
    return obj


def setup_world_and_light(plan: dict, scene, base: Path) -> None:
    sun = bpy.data.lights.new("Sun", type="SUN")
    sun.energy = plan["sun"]["strength"]
    obj = bpy.data.objects.new("Sun", sun)
    obj.rotation_euler = plan["sun"]["rotation_euler"]
    get_collection("Lights", scene).objects.link(obj)

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.color = plan["world_color"]
    if world.node_tree is None:
        world.use_nodes = True
    tree = world.node_tree
    background = next(n for n in tree.nodes if n.type == "BACKGROUND")
    background.inputs["Color"].default_value = (*plan["world_color"], 1.0)
    background.inputs["Strength"].default_value = 1.0
    if "world" in plan:  # HDRI sky
        w = plan["world"]
        env = tree.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(base / w["hdri"]["path"]), check_existing=True)
        coords = tree.nodes.new("ShaderNodeTexCoord")
        mapping = tree.nodes.new("ShaderNodeMapping")
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(w["rotation_deg"]))
        tree.links.new(coords.outputs["Generated"], mapping.inputs["Vector"])
        tree.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
        tree.links.new(env.outputs["Color"], background.inputs["Color"])
        background.inputs["Strength"].default_value = w["strength"]


def add_plant(spec: dict, scene, base: Path) -> None:
    """Import a CC0 glTF model and join its meshes into one object named by the plan."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(base / spec["model"]["path"]))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    view_layer = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    plant = view_layer.objects.active
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # join() already deleted the merged meshes; drop the remaining import helpers (empties)
    for o in [o for o in bpy.data.objects if o not in before and o != plant]:
        bpy.data.objects.remove(o)
    # stand the model on its base, centred in XY so rotation_z spins it in place
    vs = plant.data.vertices
    cx = (min(v.co.x for v in vs) + max(v.co.x for v in vs)) / 2
    cy = (min(v.co.y for v in vs) + max(v.co.y for v in vs)) / 2
    lowest = min(v.co.z for v in vs)
    for v in vs:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= lowest
    plant.name = spec["name"]
    plant.location = spec["location"]
    plant.rotation_mode = "XYZ"  # glTF import leaves QUATERNION; euler would be ignored
    plant.rotation_euler = (0.0, 0.0, spec["rotation_z"])
    plant.scale = (spec["scale"],) * 3
    for coll in list(plant.users_collection):
        coll.objects.unlink(plant)
    get_collection(spec["collection"], scene).objects.link(plant)


def setup_render(render: dict, scene, photoreal: bool = False) -> None:
    scene.render.engine = render["engine"]
    scene.render.resolution_x = render["width"]
    scene.render.resolution_y = render["height"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    if render["engine"] == "CYCLES":
        scene.cycles.samples = render["samples"]
        scene.cycles.use_denoising = render["profile"] != "smoke"
        if scene.cycles.use_denoising:
            scene.cycles.denoiser = "OPENIMAGEDENOISE"
        scene.cycles.device = render["device"] or "CPU"
    else:
        scene.eevee.taa_render_samples = render["samples"]
    # AgX keeps highlight detail for HDRI-lit photoreal scenes; flat scenes stay Standard.
    try:
        scene.view_settings.view_transform = "AgX" if photoreal else "Standard"
    except TypeError:
        scene.view_settings.view_transform = "AgX"


def main() -> None:
    args = parse_args()
    plan_path = Path(args.plan).resolve()
    base = plan_path.parent  # asset paths in the plan are relative to the revision dir
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    clear_scene()
    scene = bpy.context.scene
    materials = {m["name"]: make_material(m, base) for m in plan["materials"]}
    for spec in plan["objects"]:
        add_object(spec, scene, materials)
    for spec in plan.get("assets", []):
        add_plant(spec, scene, base)
    cameras = [add_camera(spec, scene) for spec in plan["cameras"]]
    scene.camera = cameras[0]
    setup_world_and_light(plan, scene, base)
    setup_render(plan["render"], scene, photoreal="world" in plan)

    blend = Path(args.blend)
    tmp_blend = blend.with_name(blend.stem + ".tmp.blend")
    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 backups in the revision
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_blend), check_existing=False, relative_remap=True)
    if any(img.source == "FILE" for img in bpy.data.images):
        bpy.ops.file.make_paths_relative()  # //materials/... keeps the revision portable
        bpy.ops.wm.save_mainfile()
    os.replace(tmp_blend, blend)

    glb = Path(args.glb)
    tmp_glb = glb.with_name(glb.stem + ".tmp.glb")
    bpy.ops.export_scene.gltf(
        filepath=str(tmp_glb),
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    os.replace(tmp_glb, glb)
    result = {"blend": str(blend), "glb": str(glb), "python": sys.version.split()[0]}
    print("EA_RESULT " + json.dumps(result), flush=True)


main()

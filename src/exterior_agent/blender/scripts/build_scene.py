"""Runs inside Blender: build the canonical scene from scene_plan.json, save .blend, export GLB.

Usage (fixed by exterior_agent.blender.invoke):
  blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
    --python build_scene.py -- --plan scene_plan.json --blend model.blend --glb model.glb
Only stdlib + bpy: Blender's embedded Python has no project dependencies.
"""

import argparse
import json
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


def make_material(spec: dict) -> bpy.types.Material:
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


def setup_world_and_light(plan: dict, scene) -> None:
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
    background = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    background.inputs["Color"].default_value = (*plan["world_color"], 1.0)
    background.inputs["Strength"].default_value = 1.0


def setup_render(render: dict, scene) -> None:
    scene.render.engine = render["engine"]
    scene.render.resolution_x = render["width"]
    scene.render.resolution_y = render["height"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    if render["engine"] == "CYCLES":
        scene.cycles.samples = render["samples"]
        scene.cycles.use_denoising = False
        scene.cycles.device = render["device"] or "CPU"
    else:
        scene.eevee.taa_render_samples = render["samples"]
    try:
        scene.view_settings.view_transform = "Standard"
    except TypeError:
        scene.view_settings.view_transform = "AgX"


def main() -> None:
    args = parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    clear_scene()
    scene = bpy.context.scene
    materials = {m["name"]: make_material(m) for m in plan["materials"]}
    for spec in plan["objects"]:
        add_object(spec, scene, materials)
    cameras = [add_camera(spec, scene) for spec in plan["cameras"]]
    scene.camera = cameras[0]
    setup_world_and_light(plan, scene)
    setup_render(plan["render"], scene)

    blend = Path(args.blend)
    tmp_blend = blend.with_name(blend.stem + ".tmp.blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_blend), check_existing=False, relative_remap=True)
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
    print("EA_RESULT " + json.dumps({"blend": str(blend), "glb": str(glb)}), flush=True)


main()

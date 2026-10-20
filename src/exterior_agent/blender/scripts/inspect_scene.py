"""Runs inside Blender: report scene contents of a .blend or an imported .glb as JSON.

  ... --python inspect_scene.py -- (--blend model.blend | --glb model.glb) --out report.json
      [--rays rays.json]
rays.json: [{"object", "origin", "direction", "distance"}] in world space -> list of hit booleans.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="inspect_scene.py")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--blend")
    source.add_argument("--glb")
    parser.add_argument("--out", required=True)
    parser.add_argument("--rays")
    return parser.parse_args(argv)


def load(args: argparse.Namespace) -> None:
    if args.blend:
        bpy.ops.wm.open_mainfile(filepath=args.blend, load_ui=False)
        return
    for block in list(bpy.data.objects):
        bpy.data.objects.remove(block)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block)
    bpy.ops.import_scene.gltf(filepath=args.glb)


def uv_max_error(obj) -> float:
    """Largest difference between stored UVs and the metric box projection of each face."""
    mesh = obj.data
    uv = mesh.uv_layers[0].data
    worst = 0.0
    for poly in mesh.polygons:
        axis = max(range(3), key=lambda k: abs(poly.normal[k]))
        keep = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
        for loop_index in poly.loop_indices:
            co = obj.matrix_world @ mesh.vertices[mesh.loops[loop_index].vertex_index].co
            expected = (co[keep[0]], co[keep[1]])
            got = uv[loop_index].uv
            worst = max(worst, abs(got[0] - expected[0]), abs(got[1] - expected[1]))
    return worst


def world_nodes() -> list[str]:
    world = bpy.context.scene.world
    return sorted(n.type for n in world.node_tree.nodes) if world and world.node_tree else []


def material_inputs(mat) -> dict:
    """Which node type feeds the Principled BSDF base colour (None for a plain value)."""
    tree = mat.node_tree
    bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if tree else None
    if bsdf is None or not bsdf.inputs["Base Color"].links:
        return {"base_color_from": None}
    return {"base_color_from": bsdf.inputs["Base Color"].links[0].from_node.type}


def object_entry(obj) -> dict:
    entry = {
        "type": obj.type,
        "collections": [c.name for c in obj.users_collection],
        "materials": [s.material.name for s in obj.material_slots if s.material],
    }
    if obj.type == "MESH":
        entry["uv_layers"] = len(obj.data.uv_layers)
        if obj.data.uv_layers:
            entry["uv_max_error"] = uv_max_error(obj)
    if obj.type == "MESH" and obj.data.vertices:
        world = [obj.matrix_world @ v.co for v in obj.data.vertices]
        entry["bbox_min"] = [min(v[i] for v in world) for i in range(3)]
        entry["bbox_max"] = [max(v[i] for v in world) for i in range(3)]
    return entry


def cast(ray: dict, depsgraph) -> bool:
    obj = bpy.data.objects[ray["object"]]
    bvh = BVHTree.FromObject(obj, depsgraph)  # object space
    inv = obj.matrix_world.inverted()
    origin = inv @ Vector(ray["origin"])
    direction = (inv.to_3x3() @ Vector(ray["direction"])).normalized()
    location, _normal, _index, _dist = bvh.ray_cast(origin, direction, ray["distance"])
    return location is not None


def main() -> None:
    args = parse_args()
    load(args)
    report = {
        "objects": {obj.name: object_entry(obj) for obj in bpy.data.objects},
        "cameras": {
            obj.name: {
                "projection": obj.data.type,
                "lens_mm": obj.data.lens,
                "ortho_scale": obj.data.ortho_scale,
            }
            for obj in bpy.data.objects
            if obj.type == "CAMERA"
        },
        "materials": [m.name for m in bpy.data.materials],
        "images": [
            {
                "name": img.name,
                "filepath": img.filepath,
                "exists": os.path.exists(bpy.path.abspath(img.filepath)),
            }
            for img in bpy.data.images
            if img.source == "FILE"
        ],
        "world_nodes": world_nodes(),
        "material_inputs": {m.name: material_inputs(m) for m in bpy.data.materials},
        "rays": [],
    }
    if args.rays:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        rays = json.loads(Path(args.rays).read_text(encoding="utf-8"))
        report["rays"] = [cast(ray, depsgraph) for ray in rays]
    Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


main()

"""Runs inside Blender: report scene contents of a .blend or an imported .glb as JSON.

  ... --python inspect_scene.py -- (--blend model.blend | --glb model.glb) --out report.json
      [--rays rays.json]
rays.json: [{"object", "origin", "direction", "distance"}] in world space -> list of hit booleans.
"""

import argparse
import json
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


def object_entry(obj) -> dict:
    entry = {
        "type": obj.type,
        "collections": [c.name for c in obj.users_collection],
        "materials": [s.material.name for s in obj.material_slots if s.material],
    }
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
        "rays": [],
    }
    if args.rays:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        rays = json.loads(Path(args.rays).read_text(encoding="utf-8"))
        report["rays"] = [cast(ray, depsgraph) for ray in rays]
    Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


main()

"""Runs inside Blender: render the requested cameras of model.blend one after another.

  ... --python render_views.py -- --blend model.blend --images DIR --cameras 01_front,02_rear
      [--device CPU|GPU]
Prints `EA_PROGRESS {json}` after each finished view; images appear atomically as <id>.png.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import bpy

# CUDA first: on the owner's RTX 3050 Ti (driver 566.07) OptiX kernels fail to compile
# with Blender 5.2.2 while CUDA renders (measured 2026-10-19, see docs/STATUS.md).
GPU_BACKENDS = ("CUDA", "OPTIX", "HIP", "ONEAPI", "METAL")


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(prog="render_views.py")
    parser.add_argument("--blend", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--cameras", required=True)
    parser.add_argument("--device", choices=("CPU", "GPU"))
    return parser.parse_args(argv)


def enable_gpu(scene) -> str:
    """Enable the first available Cycles GPU backend; fail loudly instead of falling back."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in GPU_BACKENDS:
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        devices = [d for d in prefs.devices if d.type == backend]
        if devices:
            for d in prefs.devices:
                d.use = d.type == backend
            scene.cycles.device = "GPU"
            return f"{backend}: " + ", ".join(d.name for d in devices)
    raise SystemExit("EA_ERROR no Cycles GPU device available")


def main() -> None:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=args.blend, load_ui=False)
    scene = bpy.context.scene
    if scene.render.engine == "CYCLES":
        if args.device == "GPU":
            print("EA_DEVICE " + json.dumps({"gpu": enable_gpu(scene)}), flush=True)
        else:
            scene.cycles.device = "CPU"
    images = Path(args.images)
    images.mkdir(parents=True, exist_ok=True)
    for cam_id in args.cameras.split(","):
        scene.camera = bpy.data.objects[f"CAM_{cam_id}"]
        tmp = images / f".tmp_{cam_id}.png"
        scene.render.filepath = str(tmp)
        start = time.monotonic()
        bpy.ops.render.render(write_still=True)
        os.replace(tmp, images / f"{cam_id}.png")
        progress = {"camera": cam_id, "status": "completed", "seconds": time.monotonic() - start}
        print("EA_PROGRESS " + json.dumps(progress), flush=True)


main()

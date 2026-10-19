"""Test double for blender.exe: understands the same command line as the real scripts.

Env: FAKE_BLENDER_FAIL=build | render:<n> (exit 1 at build, or after n rendered views)
     FAKE_BLENDER_SLEEP=<seconds> (pause before each view)
"""

import json
import os
import random
import struct
import sys
import time
from pathlib import Path

from PIL import Image


def opt(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


def write_glb(path: Path, plan: dict) -> None:
    doc = {
        "asset": {"version": "2.0"},
        "nodes": [{"name": o["name"]} for o in plan["objects"]],
        "materials": [{"name": m["name"]} for m in plan["materials"]],
    }
    chunk = json.dumps(doc).encode()
    chunk += b" " * (-len(chunk) % 4)
    body = struct.pack("<II", len(chunk), 0x4E4F534A) + chunk
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)


def build(args: list[str], fail: str) -> int:
    if fail == "build":
        print("fake build failure", flush=True)
        return 1
    plan = json.loads(Path(opt(args, "--plan")).read_text(encoding="utf-8"))
    Path(opt(args, "--blend")).write_bytes(b"FAKE-BLEND " + plan["project_id"].encode())
    write_glb(Path(opt(args, "--glb")), plan)
    print("EA_RESULT " + json.dumps({"python": "3.13.13"}), flush=True)
    return 0


def render(args: list[str], fail: str) -> int:
    blend = Path(opt(args, "--blend"))
    plan = json.loads((blend.parent / "scene_plan.json").read_text(encoding="utf-8"))
    size = (plan["render"]["width"], plan["render"]["height"])
    images = Path(opt(args, "--images"))
    images.mkdir(parents=True, exist_ok=True)
    sleep = float(os.environ.get("FAKE_BLENDER_SLEEP", "0"))
    for n, cam_id in enumerate(opt(args, "--cameras").split(",")):
        if fail == f"render:{n}":
            print("fake render failure", flush=True)
            return 1
        time.sleep(sleep)
        rng = random.Random(cam_id + plan["project_id"])
        img = Image.new("RGB", size)
        img.putdata([(rng.randrange(256),) * 3 for _ in range(size[0] * size[1])])
        tmp = images / f".tmp_{cam_id}.png"
        img.save(tmp, "PNG")
        os.replace(tmp, images / f"{cam_id}.png")
        progress = {"camera": cam_id, "status": "completed", "seconds": sleep}
        print("EA_PROGRESS " + json.dumps(progress), flush=True)
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--version" in args:
        print("Blender 5.2.2 LTS (fake)")
        return 0
    script = Path(opt(args, "--python")).name
    script_args = args[args.index("--") + 1 :]
    fail = os.environ.get("FAKE_BLENDER_FAIL", "")
    if script == "build_scene.py":
        return build(script_args, fail)
    if script == "render_views.py":
        return render(script_args, fail)
    print(f"fake blender: unsupported script {script}", flush=True)
    return 2


sys.exit(main())

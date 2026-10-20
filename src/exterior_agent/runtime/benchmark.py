"""Measure render time, VRAM and RAM per sample level on the owner's machine.

Builds the scene once, then renders the chosen views at each sample level sequentially
(one Blender process at a time) while a background thread samples GPU memory and free RAM.
"""

import json
import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from exterior_agent.assets.fetch import cache_dir
from exterior_agent.blender.invoke import blender_command, blender_version, run_blender
from exterior_agent.domain.project import Project
from exterior_agent.domain.render import RenderSettings
from exterior_agent.geometry.scene_plan import build_scene_plan
from exterior_agent.runtime.assets_stage import stage_assets
from exterior_agent.runtime.doctor import _memory
from exterior_agent.runtime.files import atomic_write_json

SAMPLE_EVERY_S = 0.5
STAGE_TIMEOUT_S = 3600.0


class BenchmarkFailed(Exception):
    pass


def sample_resources() -> dict:
    vram = None
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            out = subprocess.run(
                [exe, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.split()
            vram = int(out[0]) if out else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            vram = None
    memory = _memory()
    return {"vram_used_mib": vram, "ram_available_gb": memory and memory["available_gb"]}


class _Sampler:
    """Calls `sampler` at the start, every SAMPLE_EVERY_S while running, and at the end."""

    def __init__(self, sampler: Callable[[], dict]):
        self.sampler, self.samples = sampler, [sampler()]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(SAMPLE_EVERY_S):
            self.samples.append(self.sampler())

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        self.samples.append(self.sampler())

    def peak_vram(self) -> int | None:
        values = [s["vram_used_mib"] for s in self.samples if s["vram_used_mib"] is not None]
        return max(values) if values else None

    def min_ram(self) -> float | None:
        values = [s["ram_available_gb"] for s in self.samples if s["ram_available_gb"] is not None]
        return min(values) if values else None


def run_benchmark(
    project: Project,
    render: RenderSettings,
    samples: list[int],
    views: list[str],
    out: Path,
    blender: list[str],
    sampler: Callable[[], dict] = sample_resources,
    asset_cache: Path | None = None,
) -> dict:
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    plan = build_scene_plan(project, render)
    atomic_write_json(out / "scene_plan.json", plan)
    stage_assets(plan, asset_cache or cache_dir(), out)
    build_args = ["--plan", str(out / "scene_plan.json"), "--blend", str(out / "model.blend")]
    build_args += ["--glb", str(out / "model.glb")]
    built = run_blender(
        blender_command(blender, "build_scene.py", build_args),
        out / "logs" / "build.log",
        STAGE_TIMEOUT_S,
    )
    if built.status != "ok":
        raise BenchmarkFailed(f"scene build {built.status}; see {out / 'logs' / 'build.log'}")

    levels = []
    for level in samples:
        images = out / f"s{level}"
        seconds: dict[str, float] = {}

        def on_line(line: str, seconds=seconds) -> None:
            if line.startswith("EA_PROGRESS "):
                event = json.loads(line[12:])
                seconds[event["camera"]] = round(event["seconds"], 3)

        args = ["--blend", str(out / "model.blend"), "--images", str(images)]
        args += ["--cameras", ",".join(views), "--samples", str(level)]
        if render.engine == "CYCLES" and render.device:
            args += ["--device", render.device]
        log = out / "logs" / f"render_s{level}.log"
        cmd = blender_command(blender, "render_views.py", args)
        with _Sampler(sampler) as resources:
            result = run_blender(cmd, log, STAGE_TIMEOUT_S, on_line=on_line)
        if result.status != "ok":
            raise BenchmarkFailed(f"render at {level} samples {result.status}; see {log}")
        levels.append(
            {
                "samples": level,
                "views": seconds,
                "seconds_per_view_avg": round(sum(seconds.values()) / max(len(seconds), 1), 3),
                "vram_used_mib_peak": resources.peak_vram(),
                "ram_available_gb_min": resources.min_ram(),
                "images": {v: f"s{level}/{v}.png" for v in views},
            }
        )
    report = {
        "blender_version": blender_version(blender),
        "render": render.to_dict(),
        "levels": levels,
    }
    atomic_write_json(out / "benchmark.json", report)
    return report

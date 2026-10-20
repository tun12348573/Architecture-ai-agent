"""Build job: validate -> scene plan -> Blender build -> sequential renders -> package.

State lives in <revision>/job.json. A completed revision is never touched again; an
incomplete one resumes only when its fingerprint and recorded artifacts still match.
"""

import hashlib
import json
import os
import platform
import sys
import tempfile
import threading
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from exterior_agent import __version__
from exterior_agent.assets.fetch import cache_dir
from exterior_agent.blender.invoke import blender_command, blender_version, run_blender
from exterior_agent.domain.project import Project
from exterior_agent.domain.render import RenderSettings
from exterior_agent.domain.validate import unresolved_assumptions
from exterior_agent.geometry.scene_plan import (
    build_scene_plan,
    required_material_names,
    required_object_names,
)
from exterior_agent.runtime.assets_stage import AssetsMissing, stage_assets, write_licenses
from exterior_agent.runtime.delivery import (
    make_contact_sheet,
    validate_glb,
    validate_png,
    verify_delivery,
    write_delivery,
)
from exterior_agent.runtime.files import atomic_write_json, canonical_json, sha256_file
from exterior_agent.runtime.revision import content_hash, revision_dir

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

ARTIFACTS = ("model.blend", "model.glb")
LOCK_NAME = ".exterior-agent.lock"
# Retention policy: only these known temporary names are ever deleted.
TEMP_GLOBS = ("*.tmp", "*.tmp.blend", "*.tmp.glb", "*.blend1", "images/.tmp_*.png")
Status = Literal["completed", "failed", "cancelled"]


class ResumeRefused(Exception):
    pass


class BuildBusy(Exception):
    pass


@dataclass
class BuildOptions:
    out_dir: Path
    render: RenderSettings
    blender: list[str]
    stage_timeout_s: float = 1800.0
    cancel: threading.Event | None = None
    on_progress: Callable[[str, dict], None] | None = None
    asset_cache: Path | None = None  # None -> exterior_agent.assets.fetch.cache_dir()


@dataclass
class BuildOutcome:
    status: Status
    revision_dir: Path
    rendered_now: list[str]
    already_complete: bool
    message: str


class _StageFailed(Exception):
    def __init__(self, status: Status, message: str):
        self.status = status
        super().__init__(message)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def code_hash(root: Path | None = None) -> str:
    """Hash of every .py file of the package (host code and Blender scripts), so a resume
    never mixes outputs produced by different code under the same version number."""
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def _clean_temp(rev: Path) -> None:
    for pattern in TEMP_GLOBS:
        for path in rev.glob(pattern):
            path.unlink(missing_ok=True)


def _check_resume(rev: Path, job: dict, fingerprint: dict) -> None:
    changed = sorted(k for k in fingerprint if job.get("fingerprint", {}).get(k) != fingerprint[k])
    if changed:
        raise ResumeRefused(
            f"{rev} was started with a different {', '.join(changed)}; "
            "delete that directory or bump project_revision to rebuild"
        )
    recorded_all = job.get("artifacts", {})
    for name in ARTIFACTS:
        if recorded_all.get(name) is None and (rev / name).exists():
            raise ResumeRefused(
                f"{rev / name} exists but was not recorded by this job; not overwriting it"
            )
    for name, recorded in recorded_all.items():  # model files and staged textures
        path = rev / name
        if not path.exists() or sha256_file(path) != recorded:
            raise ResumeRefused(
                f"{path} changed since it was built (hand edit?); not overwriting it"
            )


class _Job:
    def __init__(self, project: Project, opts: BuildOptions):
        self.project, self.opts = project, opts
        # Absolute: Blender resolves relative output paths against the drive root, not the CWD.
        self.rev = revision_dir(Path(opts.out_dir).resolve(), project, opts.render)
        self.plan = build_scene_plan(project, opts.render)
        self.camera_ids = [c["id"] for c in self.plan["cameras"]]
        self.rendered_now: list[str] = []
        self.lock = threading.Lock()
        self.fingerprint = {
            "input_hash": content_hash(project, opts.render),
            "scene_plan_hash": _sha_text(canonical_json(self.plan)),
            "tool_version": __version__,
            "code_hash": code_hash(),
            "blender_version": blender_version(opts.blender),
            "render": opts.render.to_dict(),
        }
        self.state: dict = {}

    def save(self) -> None:
        with self.lock:
            self.state["updated_at"] = _now()
            atomic_write_json(self.rev / "job.json", self.state)

    def start(self) -> bool:
        """Prepare state; return False when the revision is already complete."""
        job_path = self.rev / "job.json"
        if job_path.exists():
            state = json.loads(job_path.read_text(encoding="utf-8"))
            if state.get("status") == "completed":
                return False
            _check_resume(self.rev, state, self.fingerprint)
            state["attempt"] += 1
            state["error"] = None
            self.state = state
        else:
            if self.rev.exists() and any(self.rev.iterdir()):
                raise ResumeRefused(f"{self.rev} exists without job.json; not overwriting it")
            self.state = {
                "status": "queued",
                "attempt": 1,
                "fingerprint": self.fingerprint,
                "artifacts": {},
                "stages": {},
                "views": {cid: {"status": "pending"} for cid in self.camera_ids},
                "error": None,
                "created_at": _now(),
            }
            atomic_write_json(self.rev / "project.json", self.project.model_dump(mode="json"))
            atomic_write_json(self.rev / "scene_plan.json", self.plan)
        _clean_temp(self.rev)
        self.state["status"] = "running"
        self.save()
        return True

    def run_stage(self, name: str, script: str, args: list[str], on_line=None) -> None:
        cmd = blender_command(self.opts.blender, script, args)
        log = self.rev / "logs" / f"{name}.log"
        self.state["stages"][name] = {"status": "running", "attempt": self.state["attempt"]}
        self.save()
        result = run_blender(cmd, log, self.opts.stage_timeout_s, self.opts.cancel, on_line)
        status = {"ok": "completed", "cancelled": "cancelled"}.get(result.status, "failed")
        self.state["stages"][name].update(status=status, seconds=round(result.seconds, 3))
        self.save()
        if result.status != "ok":
            detail = (
                f"exit code {result.returncode}" if result.status == "failed" else result.status
            )
            message = f"{name} stage {detail}; see {log}"
            text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
            if "out of GPU memory" in text or "CUDA error" in text:
                message += (
                    "; the GPU ran out of memory: lower --samples or plants, "
                    "or use --engine cycles --device cpu"
                )
            raise _StageFailed("cancelled" if result.status == "cancelled" else "failed", message)

    def stage_assets(self) -> None:
        cache = self.opts.asset_cache or cache_dir()
        try:
            staged = stage_assets(self.plan, cache, self.rev)
        except AssetsMissing as exc:
            raise _StageFailed("failed", str(exc)) from exc
        self.state["artifacts"].update(staged)
        self.save()

    def build(self) -> None:
        if all(name in self.state["artifacts"] for name in ARTIFACTS):
            return
        self.stage_assets()

        def on_line(line: str) -> None:
            if line.startswith("EA_RESULT "):
                self.state["blender_python"] = json.loads(line[10:]).get("python")

        self.run_stage(
            "build",
            "build_scene.py",
            [
                "--plan", str(self.rev / "scene_plan.json"),
                "--blend", str(self.rev / "model.blend"),
                "--glb", str(self.rev / "model.glb"),
            ],
            on_line,
        )  # fmt: skip
        for name in ARTIFACTS:
            if not (self.rev / name).is_file():
                raise _StageFailed("failed", f"build stage did not produce {name}")
            self.state["artifacts"][name] = sha256_file(self.rev / name)
        self.save()

    def view_done(self, cam_id: str) -> bool:
        view = self.state["views"].get(cam_id, {})
        path = self.rev / "images" / f"{cam_id}.png"
        r = self.opts.render
        return (
            view.get("status") == "completed"
            and path.is_file()
            and sha256_file(path) == view.get("sha256")
            and validate_png(path, r.width, r.height) is None
        )

    def render(self) -> None:
        pending = [cid for cid in self.camera_ids if not self.view_done(cid)]
        if not pending:
            return
        images = self.rev / "images"
        r = self.opts.render

        def on_line(line: str) -> None:
            if not line.startswith("EA_PROGRESS "):
                return
            event = json.loads(line[12:])
            cam_id = event["camera"]
            path = images / f"{cam_id}.png"
            error = validate_png(path, r.width, r.height)
            entry = {
                "status": "failed" if error else "completed",
                "path": f"images/{cam_id}.png",
                "sha256": None if error else sha256_file(path),
                "seconds": round(event.get("seconds", 0.0), 3),
                "attempt": self.state["attempt"],
                "error": error,
            }
            with self.lock:
                self.state["views"][cam_id] = entry
            self.rendered_now.append(cam_id)
            self.save()
            if self.opts.on_progress is not None:
                self.opts.on_progress(cam_id, entry)

        args = ["--blend", str(self.rev / "model.blend"), "--images", str(images)]
        args += ["--cameras", ",".join(pending)]
        if r.engine == "CYCLES" and r.device:
            args += ["--device", r.device]
        self.run_stage("render", "render_views.py", args, on_line)
        missing = [cid for cid in self.camera_ids if not self.view_done(cid)]
        if missing:
            raise _StageFailed("failed", f"views not rendered or invalid: {', '.join(missing)}")

    def package(self) -> None:
        self.state["stages"]["package"] = {"status": "running", "attempt": self.state["attempt"]}
        errors = validate_glb(
            self.rev / "model.glb",
            required_object_names(self.plan),
            required_material_names(self.plan),
        )
        for name in ARTIFACTS:
            if sha256_file(self.rev / name) != self.state["artifacts"][name]:
                errors.append(f"{name} changed during the job")
        if errors:
            raise _StageFailed("failed", "; ".join(errors))
        images = [(cid, self.rev / "images" / f"{cid}.png") for cid in self.camera_ids]
        make_contact_sheet(images, self.rev / "contact_sheet.png")
        timings = {k: v.get("seconds") for k, v in self.state["stages"].items()}
        info = {
            "project_id": self.project.project_id,
            "project_revision": self.project.project_revision,
            "label": self.project.label,
            "revision_dir": self.rev.name,
            "tool_version": __version__,
            "code_hash": self.fingerprint["code_hash"],
            "blender_version": self.fingerprint["blender_version"],
            "python_versions": {
                "host": platform.python_version(),
                "blender": self.state.get("blender_python"),
            },
            "render": self.opts.render.to_dict(),
            "complete": True,
            "views": {cid: self.state["views"][cid] for cid in self.camera_ids},
            "unresolved_assumptions": unresolved_assumptions(self.project),
            "timings_seconds": timings,
            "assets": [
                {"id": entry["id"], "license": entry["license"]} for entry in self._licenses()
            ],
            "placeholders": sorted(
                o["name"] for o in self.plan["objects"] if o["name"].startswith("Prop_")
            ),
            "packaged_at": _now(),
        }
        illustrative = _illustrative(self.plan)
        if illustrative:
            info["illustrative"] = illustrative
        write_delivery(self.rev, info)
        problems = verify_delivery(self.rev)
        if problems:
            raise _StageFailed("failed", "; ".join(problems))
        self.state["stages"]["package"]["status"] = "completed"

    def _licenses(self) -> list[dict]:
        # Regenerated from the plan at packaging time: an edited/deleted file cannot ship.
        return write_licenses(self.plan, self.rev)

    def finish(self, status: Status, message: str) -> BuildOutcome:
        self.state["status"] = status
        self.state["error"] = None if status == "completed" else message
        self.save()
        if status == "completed":
            _clean_temp(self.rev)
        return BuildOutcome(status, self.rev, list(self.rendered_now), False, message)


ILLUSTRATIVE_NOTE = "minh hoạ, không phải hiện trạng hay số đo"


def _illustrative(plan: dict) -> dict | None:
    """Street context and CC0 plants/lamps are illustration, never measured site data."""
    objects = sorted(o["name"] for o in plan["objects"] if o["collection"] == "Context")
    assets = sorted(a["name"] for a in plan.get("assets", []))
    if not objects and not assets:
        return None
    return {"note": ILLUSTRATIVE_NOTE, "objects": objects, "assets": assets}


def lock_path() -> Path:
    """One lock per machine user, whatever --out is: build and benchmark exclude each other."""
    return Path(os.environ.get("EXTERIOR_AGENT_LOCK") or Path(tempfile.gettempdir()) / LOCK_NAME)


@contextmanager
def build_lock(out_dir: Path | None = None):
    """OS-level exclusive lock: one Blender job at a time on this machine (brief §1).
    The OS releases it when the process exits, so a crash never leaves a stale lock.
    `out_dir` is accepted for call-site clarity only."""
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")  # held open for the whole job
    try:
        try:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise BuildBusy(
                f"another build or benchmark is running ({path}); wait for it to finish"
            ) from exc
        try:
            yield
        finally:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


def run_build(project: Project, opts: BuildOptions) -> BuildOutcome:
    with build_lock(Path(opts.out_dir).resolve()):
        return _run_locked(project, opts)


def _run_locked(project: Project, opts: BuildOptions) -> BuildOutcome:
    job = _Job(project, opts)
    if not job.start():
        return BuildOutcome("completed", job.rev, [], True, f"already complete: {job.rev}")
    try:
        job.build()
        job.render()
        job.package()
    except _StageFailed as exc:
        return job.finish(exc.status, str(exc))
    except KeyboardInterrupt:
        return job.finish("cancelled", "interrupted by user (Ctrl+C)")
    except Exception as exc:  # record unexpected failures in job.json, keep partial output
        job.finish("failed", f"{type(exc).__name__}: {exc}")
        raise
    return job.finish("completed", f"completed: {job.rev}")

"""Locate Blender and run fixed scripts headless as a single, cancellable subprocess."""

import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ENV_VAR = "EXTERIOR_AGENT_BLENDER"
SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
ALLOWED_SCRIPTS = frozenset({"build_scene.py", "render_views.py", "inspect_scene.py"})
POLL_S = 0.2
KILL_GRACE_S = 10.0


class BlenderNotFound(Exception):
    pass


@dataclass
class BlenderResult:
    returncode: int | None
    status: Literal["ok", "failed", "timeout", "cancelled"]
    seconds: float


def find_blender(explicit: str | None = None) -> list[str]:
    """Command prefix for Blender: --blender, then $EXTERIOR_AGENT_BLENDER, then PATH."""
    candidate = explicit or os.environ.get(ENV_VAR) or shutil.which("blender")
    if not candidate:
        raise BlenderNotFound(f"Blender not found: pass --blender PATH or set {ENV_VAR}")
    if not Path(candidate).is_file():
        raise BlenderNotFound(
            f"Blender executable does not exist: {candidate} (check --blender or {ENV_VAR})"
        )
    return [str(candidate)]


def blender_command(blender: list[str], script: str, args: list[str]) -> list[str]:
    if script not in ALLOWED_SCRIPTS:
        raise ValueError(f"unknown Blender script {script!r}")
    return [
        *blender,
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--python-exit-code",
        "1",
        "--python",
        str(SCRIPTS_DIR / script),
        "--",
        *args,
    ]


def blender_version(blender: list[str]) -> str:
    out = subprocess.run(
        [*blender, "--version"], capture_output=True, text=True, timeout=120, errors="replace"
    ).stdout
    return next((line.strip() for line in out.splitlines() if line.strip()), "unknown")


def run_blender(
    cmd: list[str],
    log_path: Path,
    timeout_s: float,
    cancel: threading.Event | None = None,
    on_line: Callable[[str], None] | None = None,
) -> BlenderResult:
    """Run without a shell, tee merged output to log_path, stop on cancel or timeout."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Own process group: a console Ctrl+C reaches only us; we stop the child deliberately.
    if sys.platform == "win32":
        group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        group = {"start_new_session": True}
    start = time.monotonic()
    with open(log_path, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            **group,
        )

        def pump() -> None:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                if on_line is not None:
                    on_line(line.rstrip("\r\n"))

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        status: Literal["ok", "failed", "timeout", "cancelled"] | None = None
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                status = "cancelled"
            elif time.monotonic() - start > timeout_s:
                status = "timeout"
            if status:
                _stop(proc)
                break
            time.sleep(POLL_S)
        reader.join(timeout=KILL_GRACE_S)
        if status is None:
            status = "ok" if proc.returncode == 0 else "failed"
        log.write(f"\n[exterior-agent] exit={proc.returncode} status={status}\n")
    return BlenderResult(proc.returncode, status, time.monotonic() - start)


def _stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

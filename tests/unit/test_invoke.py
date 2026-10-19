import sys
import threading
import time
from pathlib import Path

import pytest

from exterior_agent.blender.invoke import (
    SCRIPTS_DIR,
    BlenderNotFound,
    blender_command,
    find_blender,
    run_blender,
)


def test_blender_command_is_fixed_argument_list():
    cmd = blender_command(
        ["C:/Program Files/B/blender.exe"], "build_scene.py", ["--plan", "a b.json"]
    )
    assert cmd[0] == "C:/Program Files/B/blender.exe"
    for flag in ("--background", "--factory-startup", "--disable-autoexec"):
        assert flag in cmd
    i = cmd.index("--python-exit-code")
    assert cmd[i + 1] == "1"
    assert cmd[cmd.index("--python") + 1] == str(SCRIPTS_DIR / "build_scene.py")
    assert cmd[cmd.index("--") + 1 :] == ["--plan", "a b.json"]


def test_unknown_script_rejected():
    with pytest.raises(ValueError):
        blender_command(["blender"], "evil.py", [])


def test_find_blender_missing_env_path(monkeypatch, tmp_path):
    monkeypatch.setenv("EXTERIOR_AGENT_BLENDER", str(tmp_path / "nope" / "blender.exe"))
    with pytest.raises(BlenderNotFound, match="EXTERIOR_AGENT_BLENDER"):
        find_blender()


def test_find_blender_explicit_path(tmp_path):
    exe = tmp_path / "my blender" / "blender.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    assert find_blender(str(exe)) == [str(exe)]


def test_find_blender_nothing_configured(monkeypatch):
    monkeypatch.delenv("EXTERIOR_AGENT_BLENDER", raising=False)
    monkeypatch.setenv("PATH", "")
    with pytest.raises(BlenderNotFound, match="EXTERIOR_AGENT_BLENDER"):
        find_blender()


SLEEPER = [sys.executable, "-c", "import time; print('x', flush=True); time.sleep(30)"]


def test_run_blender_timeout(tmp_path):
    log = tmp_path / "logs" / "t.log"
    start = time.monotonic()
    result = run_blender(SLEEPER, log, timeout_s=1)
    assert result.status == "timeout"
    assert time.monotonic() - start < 15
    assert "x" in log.read_text(encoding="utf-8")


def test_run_blender_cancel_from_line_callback(tmp_path):
    cancel = threading.Event()
    result = run_blender(
        SLEEPER, tmp_path / "c.log", timeout_s=30, cancel=cancel, on_line=lambda _: cancel.set()
    )
    assert result.status == "cancelled"


def test_run_blender_failure_exit_code(tmp_path):
    result = run_blender([sys.executable, "-c", "raise SystemExit(3)"], tmp_path / "f.log", 30)
    assert (result.status, result.returncode) == ("failed", 3)


def test_run_blender_ok_collects_lines(tmp_path):
    lines: list[str] = []
    code = "print('EA_PROGRESS {}'); print('done')"
    result = run_blender([sys.executable, "-c", code], tmp_path / "o.log", 30, on_line=lines.append)
    assert result.status == "ok" and result.returncode == 0
    assert lines == ["EA_PROGRESS {}", "done"]
    assert Path(tmp_path / "o.log").exists()


def test_run_blender_callback_error_does_not_hang(tmp_path):
    # Child writes far more than a pipe buffer after the callback fails.
    code = "import sys\nfor i in range(40000): print('line', i, 'x' * 40)\n"

    def explode(_line):
        raise RuntimeError("progress handler broke")

    start = time.monotonic()
    result = run_blender([sys.executable, "-c", code], tmp_path / "e.log", 60, on_line=explode)
    assert time.monotonic() - start < 30
    assert result.status == "failed"
    log = (tmp_path / "e.log").read_text(encoding="utf-8")
    assert "progress handler broke" in log
    assert "line 39999" in log


def test_timeout_stops_whole_process_tree(tmp_path):
    # The child spawns a grandchild that inherits stdout (like a launcher or helper process).
    code = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print('started', flush=True)\n"
        "time.sleep(60)\n"
    )
    start = time.monotonic()
    result = run_blender([sys.executable, "-c", code], tmp_path / "tree.log", timeout_s=2)
    elapsed = time.monotonic() - start
    assert result.status == "timeout"
    assert elapsed < 8, f"took {elapsed:.1f}s: a grandchild kept the output pipe open"


def test_stop_falls_back_to_kill_when_tree_kill_fails(monkeypatch):
    import subprocess as sp

    import exterior_agent.blender.invoke as invoke

    proc = sp.Popen([sys.executable, "-c", "import time; time.sleep(60)"])

    def broken_run(*args, **kwargs):
        raise sp.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(invoke.subprocess, "run", broken_run)
    monkeypatch.setattr(invoke, "KILL_GRACE_S", 0.5)
    if sys.platform != "win32":
        monkeypatch.setattr(invoke.os, "killpg", lambda *a: (_ for _ in ()).throw(OSError("x")))
    invoke._stop(proc)
    assert proc.poll() is not None

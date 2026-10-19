"""Environment report: Python, packages, Blender, Cycles devices, RAM and NVIDIA VRAM.

Reports what is measured; it never claims render performance.
"""

import ctypes
import json
import platform
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PROBE_TIMEOUT_S = 180
# Runs inside Blender via --python-expr; stdlib + bpy only.
BLENDER_PROBE = """
import json, sys, bpy
devices = {}
prefs = bpy.context.preferences.addons["cycles"].preferences
for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
    try:
        prefs.compute_device_type = kind
    except TypeError:
        continue
    prefs.get_devices()
    found = [d.name for d in prefs.devices if d.type == kind]
    if found:
        devices[kind] = found
print("EA_DOCTOR " + json.dumps({"python": sys.version.split()[0], "cycles_devices": devices}))
"""


def _package(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _memory() -> dict | None:
    if sys.platform == "win32":

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        total, available = status.ullTotalPhys, status.ullAvailPhys
    else:
        try:
            info = dict(
                line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()
            )
        except OSError:
            return None
        total = int(info["MemTotal"].split()[0]) * 1024
        available = int(info.get("MemAvailable", info["MemFree"]).split()[0]) * 1024
    return {"total_gb": round(total / 2**30, 2), "available_gb": round(available / 2**30, 2)}


def _nvidia_smi() -> list[str] | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    query = "--query-gpu=name,memory.total,memory.used,driver_version"
    try:
        out = subprocess.run(
            [exe, query, "--format=csv,noheader"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return [line.strip() for line in out.stdout.splitlines() if line.strip()] or None


def _blender(blender: list[str] | None, not_found: str | None) -> dict:
    if blender is None:
        return {"found": False, "error": not_found}
    report: dict = {"found": True, "path": blender[-1]}
    cmd = [*blender, "--background", "--factory-startup", "--disable-autoexec"]
    try:
        version_out = subprocess.run(
            [*blender, "--version"], capture_output=True, text=True, timeout=PROBE_TIMEOUT_S
        ).stdout
        report["version"] = next((s.strip() for s in version_out.splitlines() if s.strip()), None)
        probe = subprocess.run(
            [*cmd, "--python-expr", BLENDER_PROBE],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=PROBE_TIMEOUT_S,
        ).stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        report["error"] = str(exc)
        return report
    line = next((s for s in probe.splitlines() if s.startswith("EA_DOCTOR ")), None)
    if line:
        report.update(json.loads(line[len("EA_DOCTOR ") :]))
    else:
        report["error"] = "Blender probe printed no result"
    return report


def collect(blender: list[str] | None, not_found: str | None = None) -> dict:
    return {
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "platform": platform.platform(),
        "packages": {"pydantic": _package("pydantic"), "pillow": _package("pillow")},
        "blender": _blender(blender, not_found),
        "memory": _memory(),
        "gpu_nvidia_smi": _nvidia_smi(),
    }

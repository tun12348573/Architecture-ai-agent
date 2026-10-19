"""Command line: validate | build | doctor.

Exit codes: 0 ok, 1 build failed, 2 invalid input/usage/resume refused, 3 Blender not found,
130 cancelled (Ctrl+C).
"""

import argparse
import json
import sys
from pathlib import Path

from exterior_agent import __version__
from exterior_agent.blender.invoke import BlenderNotFound, find_blender
from exterior_agent.domain.render import PROFILES, resolve_render
from exterior_agent.domain.validate import (
    ProjectValidationError,
    ValidationIssue,
    load_project,
    unresolved_assumptions,
)
from exterior_agent.runtime import doctor
from exterior_agent.runtime.runner import BuildBusy, BuildOptions, ResumeRefused, run_build

EXIT_OK, EXIT_FAILED, EXIT_INPUT, EXIT_NO_BLENDER, EXIT_CANCELLED = 0, 1, 2, 3, 130


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def _load(path: Path):
    try:
        if not path.is_file():
            raise ProjectValidationError([ValidationIssue("$", f"file not found: {path}")])
        return load_project(path)
    except ProjectValidationError as exc:
        for issue in exc.issues:
            _err(f"ERROR {issue.path}: {issue.message}")
        return None


def cmd_validate(args) -> int:
    project = _load(args.project)
    if project is None:
        return EXIT_INPUT
    print(f"OK {project.project_id} r{project.project_revision:03d} ({project.label})")
    for path in unresolved_assumptions(project):
        print(f"needs_review: {path}")
    return EXIT_OK


def cmd_build(args) -> int:
    project = _load(args.project)
    if project is None:
        return EXIT_INPUT
    try:
        render = resolve_render(
            args.profile or project.render_profile, args.engine, args.device, args.samples
        )
    except ValueError as exc:
        _err(f"ERROR render: {exc}")
        return EXIT_INPUT
    try:
        blender = find_blender(args.blender)
    except BlenderNotFound as exc:
        _err(f"ERROR {exc}")
        return EXIT_NO_BLENDER
    unresolved = unresolved_assumptions(project)
    if unresolved:
        print(f"WARNING {len(unresolved)} values need review (listed in delivery.json)")
    total = len(project.cameras)
    done: list[str] = []

    def progress(cam_id: str, entry: dict) -> None:
        done.append(cam_id)
        state = entry["status"] if not entry.get("error") else f"failed: {entry['error']}"
        print(f"[{len(done)}/{total}] {cam_id} {state} ({entry['seconds']:.1f}s)", flush=True)

    opts = BuildOptions(
        out_dir=args.out,
        render=render,
        blender=blender,
        stage_timeout_s=args.stage_timeout,
        on_progress=progress,
    )
    print(f"Building {project.project_id} r{project.project_revision:03d} [{render.profile}]")
    try:
        outcome = run_build(project, opts)
    except ResumeRefused as exc:
        _err(f"ERROR resume refused: {exc}")
        return EXIT_INPUT
    except BlenderNotFound as exc:
        _err(f"ERROR {exc}")
        return EXIT_NO_BLENDER
    except BuildBusy as exc:
        _err(f"ERROR {exc}")
        return EXIT_INPUT
    except KeyboardInterrupt:
        _err("cancelled")
        return EXIT_CANCELLED
    if outcome.status == "completed":
        prefix = "already completed" if outcome.already_complete else "completed"
        print(f"{prefix}: {outcome.revision_dir}")
        return EXIT_OK
    _err(f"{outcome.status}: {outcome.message}")
    _err(f"partial output kept in {outcome.revision_dir}; rerun the same command to resume")
    return EXIT_CANCELLED if outcome.status == "cancelled" else EXIT_FAILED


def cmd_doctor(args) -> int:
    try:
        blender, not_found = find_blender(args.blender), None
    except BlenderNotFound as exc:
        blender, not_found = None, str(exc)
    report = doctor.collect(blender, not_found)
    if args.json:
        print(json.dumps(report, indent=2))
        return EXIT_OK
    b, mem = report["blender"], report["memory"] or {}
    print(f"Python      {report['python']['version']} ({report['python']['executable']})")
    print(f"Packages    {report['packages']}")
    print(f"Blender     {b.get('version') or 'NOT FOUND'} {b.get('path', '')}")
    if b.get("error"):
        print(f"            {b['error']}")
    print(f"Blender Py  {b.get('python')}")
    print(f"Cycles GPU  {b.get('cycles_devices') or 'none detected'}")
    print(f"RAM         {mem.get('total_gb')} GB total, {mem.get('available_gb')} GB available")
    print(f"nvidia-smi  {report['gpu_nvidia_smi'] or 'not available'}")
    a = report["assets"]
    state = a.get("error") or f"{a.get('missing_files')} files missing"
    print(f"Assets      {a.get('cache')} — {state}")
    return EXIT_OK


def cmd_assets_fetch(args) -> int:
    from exterior_agent.assets import fetch as asset_fetch
    from exterior_agent.assets.catalog import load_catalog

    try:
        catalog = load_catalog(args.catalog)
    except (OSError, ValueError) as exc:
        _err(f"ERROR catalog: {exc}")
        return EXIT_INPUT
    cache = asset_fetch.cache_dir(args.cache)
    report = asset_fetch.fetch_assets(catalog, cache, download=asset_fetch.download_https)
    print(f"cache {cache}: {len(report.downloaded)} downloaded, {len(report.skipped)} up to date")
    for line in report.failed:
        _err(f"FAILED {line}")
    return EXIT_FAILED if report.failed else EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="exterior-agent")
    parser.add_argument("--version", action="version", version=f"exterior-agent {__version__}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("validate", help="validate and normalize a project.json")
    p.add_argument("project", type=Path)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("build", help="build, render and package a new revision")
    p.add_argument("project", type=Path)
    p.add_argument("--out", type=Path, default=Path("output"))
    p.add_argument("--profile", choices=sorted(PROFILES))
    p.add_argument("--engine", choices=("eevee", "cycles"))
    p.add_argument("--device", choices=("cpu", "gpu"))
    p.add_argument("--blender", help="path to blender.exe (else $EXTERIOR_AGENT_BLENDER or PATH)")
    p.add_argument("--stage-timeout", type=float, default=1800.0, help="seconds per stage")
    p.add_argument("--samples", type=int, help="override the profile's render samples")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("assets", help="manage CC0 assets (textures, HDRI, models)")
    asub = p.add_subparsers(dest="assets_command", required=True)
    f = asub.add_parser("fetch", help="download and verify every catalog asset into the cache")
    f.add_argument("--catalog", type=Path)
    f.add_argument("--cache", help="cache dir (else $EXTERIOR_AGENT_ASSETS or the default)")
    f.set_defaults(func=cmd_assets_fetch)

    p = sub.add_parser("doctor", help="report Python/Blender/GPU/RAM environment")
    p.add_argument("--blender")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_INPUT
    return args.func(args)

import _thread
import json
import sys
import threading
import time
from pathlib import Path

import pytest

from exterior_agent.domain.project import CANONICAL_CAMERA_IDS
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.runtime.delivery import verify_delivery
from exterior_agent.runtime.revision import content_hash, revision_dir
from exterior_agent.runtime.runner import BuildOptions, ResumeRefused, run_build

FAKE_BLENDER = [
    sys.executable,
    str(Path(__file__).resolve().parents[1] / "fakes" / "fake_blender.py"),
]
SMOKE = resolve_render("smoke")


@pytest.fixture
def project(demo_data):
    return parse_project(demo_data)


@pytest.fixture(autouse=True)
def clean_fake_env(monkeypatch):
    monkeypatch.delenv("FAKE_BLENDER_FAIL", raising=False)
    monkeypatch.delenv("FAKE_BLENDER_SLEEP", raising=False)
    monkeypatch.delenv("FAKE_BLENDER_HANG_AFTER", raising=False)


def options(out: Path, **kwargs) -> BuildOptions:
    return BuildOptions(out_dir=out, render=SMOKE, blender=FAKE_BLENDER, **kwargs)


def job(rev: Path) -> dict:
    return json.loads((rev / "job.json").read_text(encoding="utf-8"))


def test_revision_dir_name(project, tmp_path):
    rev = revision_dir(tmp_path, project, SMOKE)
    assert rev.parent == tmp_path / "demo-townhouse"
    assert rev.name == f"r002-{content_hash(project, SMOKE)[:8]}"
    assert content_hash(project, SMOKE) != content_hash(project, resolve_render("preview"))


def test_build_completes_and_packages(project, tmp_path):
    outcome = run_build(project, options(tmp_path))
    rev = outcome.revision_dir
    assert outcome.status == "completed" and not outcome.already_complete
    assert outcome.rendered_now == list(CANONICAL_CAMERA_IDS)
    assert sorted(p.name for p in (rev / "images").iterdir()) == [
        f"{c}.png" for c in CANONICAL_CAMERA_IDS
    ]
    for name in (
        "model.blend",
        "model.glb",
        "contact_sheet.png",
        "project.json",
        "scene_plan.json",
    ):
        assert (rev / name).is_file(), name
    assert verify_delivery(rev) == []
    delivery = json.loads((rev / "delivery.json").read_text(encoding="utf-8"))
    assert delivery["complete"] is True
    assert delivery["unresolved_assumptions"] == []
    assert delivery["blender_version"] == "Blender 5.2.2 LTS (fake)"
    assert delivery["render"] == SMOKE.to_dict()
    state = job(rev)
    assert state["status"] == "completed"
    assert all(v["status"] == "completed" for v in state["views"].values())
    assert set(state["stages"]) == {"build", "render", "package"}
    assert not [p for p in rev.rglob("*") if ".tmp" in p.name]


def test_rerun_completed_is_noop(project, tmp_path):
    rev = run_build(project, options(tmp_path)).revision_dir
    before = {p: p.stat().st_mtime_ns for p in rev.rglob("*") if p.is_file()}
    again = run_build(project, options(tmp_path))
    assert again.already_complete and again.rendered_now == [] and again.status == "completed"
    assert {p: p.stat().st_mtime_ns for p in rev.rglob("*") if p.is_file()} == before


def test_changed_parameters_create_new_revision(project, demo_data, tmp_path):
    first = run_build(project, options(tmp_path)).revision_dir
    before = {p: p.stat().st_mtime_ns for p in first.rglob("*") if p.is_file()}
    demo_data["building"]["wall_height"]["value"] = 3.2
    second = run_build(parse_project(demo_data), options(tmp_path))
    assert second.status == "completed" and second.revision_dir != first
    assert {p: p.stat().st_mtime_ns for p in first.rglob("*") if p.is_file()} == before


def test_build_failure_marks_failed_keeps_logs(project, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BLENDER_FAIL", "build")
    outcome = run_build(project, options(tmp_path))
    rev = outcome.revision_dir
    assert outcome.status == "failed"
    assert "fake build failure" in (rev / "logs" / "build.log").read_text(encoding="utf-8")
    assert not (rev / "delivery.json").exists()
    assert job(rev)["status"] == "failed" and job(rev)["error"]


def test_render_failure_keeps_partial_and_resumes(project, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BLENDER_FAIL", "render:3")
    failed = run_build(project, options(tmp_path))
    assert failed.status == "failed" and failed.rendered_now == list(CANONICAL_CAMERA_IDS[:3])
    kept = {
        c: (failed.revision_dir / "images" / f"{c}.png").stat().st_mtime_ns
        for c in CANONICAL_CAMERA_IDS[:3]
    }
    monkeypatch.delenv("FAKE_BLENDER_FAIL")
    resumed = run_build(project, options(tmp_path))
    assert resumed.status == "completed"
    assert resumed.rendered_now == list(CANONICAL_CAMERA_IDS[3:])
    for c, mtime in kept.items():
        assert (resumed.revision_dir / "images" / f"{c}.png").stat().st_mtime_ns == mtime
    assert job(resumed.revision_dir)["attempt"] == 2
    assert job(resumed.revision_dir)["views"]["01_front"]["attempt"] == 1
    assert job(resumed.revision_dir)["views"]["10_aerial"]["attempt"] == 2


def test_cancel_keeps_partial_then_resume(project, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BLENDER_SLEEP", "0.5")
    cancel = threading.Event()
    outcome = run_build(
        project, options(tmp_path, cancel=cancel, on_progress=lambda *_: cancel.set())
    )
    assert outcome.status == "cancelled"
    done = outcome.rendered_now
    assert 1 <= len(done) < 10
    assert job(outcome.revision_dir)["status"] == "cancelled"
    monkeypatch.setenv("FAKE_BLENDER_SLEEP", "0")
    resumed = run_build(project, options(tmp_path))
    assert resumed.status == "completed"
    assert set(resumed.rendered_now).isdisjoint(done)
    assert len(resumed.rendered_now) == 10 - len(done)


def test_ctrl_c_stops_blender_and_marks_cancelled(project, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BLENDER_SLEEP", "0.5")
    outcome = run_build(project, options(tmp_path, on_progress=lambda *_: _thread.interrupt_main()))
    assert outcome.status == "cancelled"
    images = outcome.revision_dir / "images"
    count = len(list(images.glob("*.png")))
    time.sleep(1.5)  # a still-running Blender would keep adding images
    assert len(list(images.glob("*.png"))) == count < 10


def test_resume_refused_on_fingerprint_mismatch(project, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BLENDER_FAIL", "render:2")
    rev = run_build(project, options(tmp_path)).revision_dir
    monkeypatch.delenv("FAKE_BLENDER_FAIL")
    state = job(rev)
    state["fingerprint"]["blender_version"] = "Blender 4.5.0"
    (rev / "job.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ResumeRefused, match="blender_version"):
        run_build(project, options(tmp_path))


def test_hand_edited_blend_is_never_overwritten(project, tmp_path, monkeypatch):
    rev = run_build(project, options(tmp_path)).revision_dir
    with open(rev / "model.blend", "ab") as f:
        f.write(b"OWNER EDIT")
    assert run_build(project, options(tmp_path)).already_complete
    assert (rev / "model.blend").read_bytes().endswith(b"OWNER EDIT")

    monkeypatch.setenv("FAKE_BLENDER_FAIL", "render:1")
    other = tmp_path / "other"
    failed_rev = run_build(project, options(other)).revision_dir
    monkeypatch.delenv("FAKE_BLENDER_FAIL")
    with open(failed_rev / "model.blend", "ab") as f:
        f.write(b"OWNER EDIT")
    with pytest.raises(ResumeRefused, match="model.blend"):
        run_build(project, options(other))
    assert (failed_rev / "model.blend").read_bytes().endswith(b"OWNER EDIT")


def test_relative_out_dir_passes_absolute_paths_to_blender(project, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outcome = run_build(project, options(Path("rel out")))
    assert outcome.status == "completed", outcome.message
    assert outcome.revision_dir.is_absolute()
    assert outcome.revision_dir.is_relative_to(tmp_path)


def test_build_with_spaces_in_paths(project, tmp_path):
    outcome = run_build(project, options(tmp_path / "my out dir"))
    assert outcome.status == "completed"
    assert " " in str(outcome.revision_dir)


def test_code_hash_tracks_source_files(tmp_path):
    from exterior_agent.runtime.runner import code_hash

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x = 1\n")
    first = code_hash(tmp_path)
    assert first == code_hash(tmp_path)
    (tmp_path / "pkg" / "a.py").write_text("x = 2\n")
    assert code_hash(tmp_path) != first


def test_resume_refused_when_code_changed(project, tmp_path, monkeypatch):
    import exterior_agent.runtime.runner as runner

    monkeypatch.setenv("FAKE_BLENDER_FAIL", "render:2")
    rev = run_build(project, options(tmp_path)).revision_dir
    monkeypatch.delenv("FAKE_BLENDER_FAIL")
    assert job(rev)["fingerprint"]["code_hash"] == runner.code_hash()
    monkeypatch.setattr(runner, "code_hash", lambda root=None: "edited-render-script")
    with pytest.raises(ResumeRefused, match="code_hash"):
        run_build(project, options(tmp_path))


def test_delivery_records_code_hash(project, tmp_path):
    from exterior_agent.runtime.runner import code_hash

    rev = run_build(project, options(tmp_path)).revision_dir
    delivery = json.loads((rev / "delivery.json").read_text(encoding="utf-8"))
    assert delivery["code_hash"] == code_hash()


def test_concurrent_build_refused(project, tmp_path):
    from exterior_agent.runtime.runner import BuildBusy, build_lock

    with build_lock(tmp_path):
        with pytest.raises(BuildBusy, match="another build"):
            run_build(project, options(tmp_path))
    assert run_build(project, options(tmp_path)).status == "completed"


def test_stage_timeout_marks_failed_and_keeps_partial(project, tmp_path, monkeypatch):
    # Hang after one view: only the render stage can time out, however slow the machine is.
    monkeypatch.setenv("FAKE_BLENDER_HANG_AFTER", "1")
    outcome = run_build(project, options(tmp_path, stage_timeout_s=8))
    assert outcome.status == "failed"
    assert "timeout" in outcome.message
    state = job(outcome.revision_dir)
    assert state["status"] == "failed" and state["stages"]["render"]["status"] == "failed"
    assert outcome.rendered_now == ["01_front"]
    monkeypatch.delenv("FAKE_BLENDER_HANG_AFTER")
    resumed = run_build(project, options(tmp_path))
    assert resumed.status == "completed"
    assert set(resumed.rendered_now).isdisjoint(outcome.rendered_now)


def test_delivery_lists_unresolved_assumptions(demo_data, tmp_path):
    demo_data["building"]["wall_thickness"]["status"] = "needs_review"
    rev = run_build(parse_project(demo_data), options(tmp_path)).revision_dir
    delivery = json.loads((rev / "delivery.json").read_text(encoding="utf-8"))
    assert delivery["unresolved_assumptions"] == ["building.wall_thickness"]

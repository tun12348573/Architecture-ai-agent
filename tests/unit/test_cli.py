import json
import sys
from pathlib import Path

import pytest

import exterior_agent.cli.main as cli
from exterior_agent.runtime.runner import ResumeRefused
from tests.unit.conftest import DEMO_PATH

FAKE_BLENDER = [
    sys.executable,
    str(Path(__file__).resolve().parents[1] / "fakes" / "fake_blender.py"),
]


@pytest.fixture
def no_blender(monkeypatch):
    monkeypatch.delenv("EXTERIOR_AGENT_BLENDER", raising=False)
    monkeypatch.setenv("PATH", "")


def test_validate_demo_exit_0(capsys):
    assert cli.main(["validate", str(DEMO_PATH)]) == 0
    out = capsys.readouterr().out
    assert "OK demo-townhouse r002" in out
    assert "needs_review:" not in out


def test_validate_lists_needs_review(demo_data, tmp_path, capsys):
    demo_data["building"]["wall_thickness"]["status"] = "needs_review"
    path = tmp_path / "p.json"
    path.write_text(json.dumps(demo_data), encoding="utf-8")
    assert cli.main(["validate", str(path)]) == 0
    assert "needs_review: building.wall_thickness" in capsys.readouterr().out


def test_validate_invalid_exit_2(demo_data, tmp_path, capsys):
    demo_data["building"]["footprint_depth"]["value"] = 12.5
    path = tmp_path / "p.json"
    path.write_text(json.dumps(demo_data), encoding="utf-8")
    assert cli.main(["validate", str(path)]) == 2
    assert "ERROR site.depth" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("content", "code"),
    [(b"{bad", 2), (b"[]", 2), (b"\xef\xbb\xbf" + DEMO_PATH.read_bytes(), 0), (b"\xff\xfe", 2)],
    ids=["syntax", "list", "bom", "binary"],
)
def test_validate_malformed_json_exit_2(tmp_path, capsys, content, code):
    path = tmp_path / "p.json"
    path.write_bytes(content)
    assert cli.main(["validate", str(path)]) == code
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err


def test_validate_missing_file_exit_2(tmp_path, capsys):
    assert cli.main(["validate", str(tmp_path / "nope.json")]) == 2
    assert "ERROR" in capsys.readouterr().err


def test_build_without_blender_exit_3(no_blender, tmp_path, capsys):
    assert cli.main(["build", str(DEMO_PATH), "--out", str(tmp_path)]) == 3
    assert "EXTERIOR_AGENT_BLENDER" in capsys.readouterr().err


def test_build_with_fake_blender_exit_0(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "find_blender", lambda explicit=None: FAKE_BLENDER)
    code = cli.main(
        ["build", str(DEMO_PATH), "--out", str(tmp_path / "o u t"), "--profile", "smoke"]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    assert "completed" in out and "o u t" in out
    assert "10_aerial" in out  # per-view progress lines


def test_build_resume_refused_exit_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "find_blender", lambda explicit=None: FAKE_BLENDER)

    def refuse(*_args, **_kwargs):
        raise ResumeRefused("hand edited")

    monkeypatch.setattr(cli, "run_build", refuse)
    assert cli.main(["build", str(DEMO_PATH), "--out", str(tmp_path)]) == 2
    assert "hand edited" in capsys.readouterr().err


def test_build_bad_render_option_exit_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "find_blender", lambda explicit=None: FAKE_BLENDER)
    assert cli.main(["build", str(DEMO_PATH), "--device", "gpu", "--out", str(tmp_path)]) == 2
    assert "cycles" in capsys.readouterr().err


def test_doctor_without_blender(no_blender, capsys):
    assert cli.main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["blender"]["found"] is False
    assert report["python"]["version"].startswith("3.13")
    assert report["memory"]["total_gb"] > 0
    assert report["packages"]["pydantic"]


def test_build_with_non_executable_blender_exit_3(monkeypatch, tmp_path, capsys):
    fake = tmp_path / "blender.txt"
    fake.write_text("not a program")
    monkeypatch.setenv("EXTERIOR_AGENT_BLENDER", str(fake))
    code = cli.main(["build", str(DEMO_PATH), "--out", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert code == 3
    assert "EXTERIOR_AGENT_BLENDER" in captured.err
    assert "Traceback" not in captured.out + captured.err


def test_build_busy_exit_2(monkeypatch, tmp_path, capsys):
    from exterior_agent.runtime.runner import BuildBusy

    monkeypatch.setattr(cli, "find_blender", lambda explicit=None: FAKE_BLENDER)

    def busy(*_args, **_kwargs):
        raise BuildBusy("another build is running")

    monkeypatch.setattr(cli, "run_build", busy)
    assert cli.main(["build", str(DEMO_PATH), "--out", str(tmp_path)]) == 2
    assert "another build" in capsys.readouterr().err

import json
import sys
from pathlib import Path

import pytest

import exterior_agent.cli.main as cli
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.runtime.benchmark import run_benchmark

FAKE_BLENDER = [
    sys.executable,
    str(Path(__file__).resolve().parents[1] / "fakes" / "fake_blender.py"),
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("FAKE_BLENDER_FAIL", "FAKE_BLENDER_SLEEP", "FAKE_BLENDER_OOM"):
        monkeypatch.delenv(key, raising=False)


def run(demo_data, tmp_path, sampler, samples=(64, 128), views=("01_front", "10_aerial")):
    return run_benchmark(
        parse_project(demo_data), resolve_render("smoke"), list(samples), list(views),
        tmp_path / "bench", FAKE_BLENDER, sampler=sampler,
    )  # fmt: skip


def test_levels_timed_and_sampled(demo_data, tmp_path):
    result = run(demo_data, tmp_path, lambda: {"vram_used_mib": 512, "ram_available_gb": 3.0})
    assert [lv["samples"] for lv in result["levels"]] == [64, 128]
    for level in result["levels"]:
        assert set(level["views"]) == {"01_front", "10_aerial"}
        assert level["seconds_per_view_avg"] >= 0
        assert level["vram_used_mib_peak"] == 512 and level["ram_available_gb_min"] == 3.0
        for path in level["images"].values():
            assert (tmp_path / "bench" / path).is_file()
    saved = json.loads((tmp_path / "bench" / "benchmark.json").read_text(encoding="utf-8"))
    assert saved == result and result["blender_version"].startswith("Blender")


def test_without_gpu_counter(demo_data, tmp_path):
    result = run(demo_data, tmp_path, lambda: {"vram_used_mib": None, "ram_available_gb": 2.5},
                 samples=(32,))  # fmt: skip
    assert result["levels"][0]["vram_used_mib_peak"] is None


def test_renders_never_overlap(demo_data, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BLENDER_LOCKCHECK", str(tmp_path / "blender.lock"))
    result = run(demo_data, tmp_path, lambda: {"vram_used_mib": 1, "ram_available_gb": 1.0},
                 samples=(16, 32, 64))  # fmt: skip
    assert len(result["levels"]) == 3


@pytest.mark.parametrize("samples", ["64,abc", "0", "64,-1", ""])
def test_cli_rejects_bad_samples(samples, capsys):
    code = cli.main(["benchmark", "examples/demo_house/project.json", "--samples", samples])
    assert code == 2


def test_cli_rejects_unknown_view(capsys):
    code = cli.main(["benchmark", "examples/demo_house/project.json", "--views", "99_nowhere"])
    assert code == 2

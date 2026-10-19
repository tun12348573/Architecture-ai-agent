import hashlib
import json
import sys
from pathlib import Path

import pytest

import exterior_agent.cli.main as cli
from exterior_agent.assets.catalog import DEFAULT_CATALOG, Catalog
from exterior_agent.assets.fetch import fetch_assets
from exterior_agent.domain.render import resolve_render
from exterior_agent.domain.validate import parse_project
from exterior_agent.runtime.delivery import verify_delivery
from exterior_agent.runtime.runner import BuildOptions, ResumeRefused, run_build

FAKE_BLENDER = [
    sys.executable,
    str(Path(__file__).resolve().parents[1] / "fakes" / "fake_blender.py"),
]


@pytest.fixture
def fake_catalog(tmp_path, monkeypatch):
    """Same ids/roles/paths as the real catalog, tiny file contents."""
    real = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
    blobs = {}
    for asset in real["assets"]:
        for f in asset["files"]:
            data = f"{asset['id']}/{f['path']}".encode()
            blobs[f["url"]] = data
            f["size"], f["sha256"] = len(data), hashlib.sha256(data).hexdigest()
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(real), encoding="utf-8")
    monkeypatch.setenv("EXTERIOR_AGENT_CATALOG", str(path))
    for key in ("FAKE_BLENDER_FAIL", "FAKE_BLENDER_SLEEP", "FAKE_BLENDER_OOM"):
        monkeypatch.delenv(key, raising=False)
    return Catalog.model_validate(real), blobs


def fill(cache, fake_catalog):
    catalog, blobs = fake_catalog
    report = fetch_assets(
        catalog, cache, download=lambda url, target: target.write_bytes(blobs[url])
    )
    assert not report.failed


def build(modern_data, tmp_path, profile="preview", cache=None, **kw):
    options = BuildOptions(
        out_dir=tmp_path / "out", render=resolve_render(profile), blender=FAKE_BLENDER,
        asset_cache=cache if cache is not None else tmp_path / "empty cache", **kw,
    )  # fmt: skip
    return run_build(parse_project(modern_data), options)


def test_build_fails_without_cached_assets(fake_catalog, modern_data, tmp_path):
    outcome = build(modern_data, tmp_path)
    assert outcome.status == "failed"
    assert "exterior-agent assets fetch" in outcome.message
    assert not (outcome.revision_dir / "logs" / "build.log").exists()


def test_textures_staged_and_licensed(fake_catalog, modern_data, tmp_path):
    cache = tmp_path / "cache"
    fill(cache, fake_catalog)
    outcome = build(modern_data, tmp_path, cache=cache)
    rev = outcome.revision_dir
    assert outcome.status == "completed", outcome.message
    staged = rev / "materials" / "painted_plaster_wall"
    assert staged.is_dir()
    for f in staged.iterdir():
        assert f.read_bytes() == (cache / "painted_plaster_wall" / f.name).read_bytes()
    licenses = json.loads((rev / "materials" / "LICENSES.json").read_text(encoding="utf-8"))
    ids = {entry["id"] for entry in licenses}
    assert {"painted_plaster_wall", "kloofendal_48d_partly_cloudy_puresky", "shrub_01"} <= ids
    assert all(entry["license"] == "CC0" for entry in licenses)
    assert verify_delivery(rev) == []
    delivery = json.loads((rev / "delivery.json").read_text(encoding="utf-8"))
    assert {a["id"] for a in delivery["assets"]} == ids
    assert "Prop_Car" in delivery["placeholders"]


def test_smoke_build_without_cache(fake_catalog, modern_data, tmp_path):
    outcome = build(modern_data, tmp_path, profile="smoke")
    assert outcome.status == "completed", outcome.message
    assert not (outcome.revision_dir / "materials").exists()


def test_edited_texture_detected(fake_catalog, modern_data, tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    fill(cache, fake_catalog)
    rev = build(modern_data, tmp_path, cache=cache).revision_dir
    texture = next((rev / "materials" / "concrete").iterdir())
    texture.write_bytes(b"owner edit")
    assert any("concrete" in e for e in verify_delivery(rev))

    monkeypatch.setenv("FAKE_BLENDER_FAIL", "render:1")
    other = tmp_path / "second"
    failed = build(modern_data, other, cache=cache)
    assert failed.status == "failed"
    monkeypatch.delenv("FAKE_BLENDER_FAIL")
    next((failed.revision_dir / "materials" / "concrete").iterdir()).write_bytes(b"edit")
    with pytest.raises(ResumeRefused):
        build(modern_data, other, cache=cache)


def test_gpu_oom_hint(fake_catalog, modern_data, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BLENDER_OOM", "1")
    cache = tmp_path / "cache"
    fill(cache, fake_catalog)
    outcome = build(modern_data, tmp_path, cache=cache)
    assert outcome.status == "failed"
    assert "--samples" in outcome.message and "--device cpu" in outcome.message


def test_samples_override(capsys):
    assert resolve_render("final", samples=64).samples == 64
    with pytest.raises(ValueError):
        resolve_render("final", samples=0)
    assert cli.main(["build", "examples/modern_townhouse/project.json", "--samples", "0"]) == 2

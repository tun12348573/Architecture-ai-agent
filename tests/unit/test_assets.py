import hashlib
import json

import pytest
from pydantic import ValidationError

import exterior_agent.cli.main as cli
from exterior_agent.assets.catalog import Catalog
from exterior_agent.assets.fetch import cached_path, fetch_assets, verify_cached

BASE = "https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/demo_tex"
BLOBS = {
    f"{BASE}/demo_tex_diff_1k.jpg": b"diffuse-bytes",
    f"{BASE}/demo_tex_rough_1k.jpg": b"rough",
}


def file_entry(url, role, data=None):
    data = BLOBS[url] if data is None else data
    return {
        "path": url.rsplit("/", 1)[1],
        "url": url,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "role": role,
    }


def catalog_dict(**overrides) -> dict:
    asset = {
        "id": "demo_tex",
        "kind": "texture",
        "license": "CC0",
        "authors": ["Someone"],
        "source_page": "https://polyhaven.com/a/demo_tex",
        "resolution": "1k",
        "scale_m": 2.0,
        "files": [
            file_entry(f"{BASE}/demo_tex_diff_1k.jpg", "base_color"),
            file_entry(f"{BASE}/demo_tex_rough_1k.jpg", "roughness"),
        ],
    }
    asset.update(overrides)
    return {"schema": "asset_catalog/1", "assets": [asset]}


class FakeDownload:
    def __init__(self, blobs=BLOBS):
        self.blobs, self.calls = dict(blobs), []

    def __call__(self, url, target):
        self.calls.append(url)
        target.write_bytes(self.blobs[url])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda f: f.update(path="../x.jpg"),
        lambda f: f.update(path="/abs.jpg"),
        lambda f: f.update(path="C:/x.jpg"),
        lambda f: f.update(path="a\\b.jpg"),
        lambda f: f.update(url="http://dl.polyhaven.org/a.jpg"),
        lambda f: f.update(url="https://evil.example/a.jpg"),
        lambda f: f.update(sha256="abc"),
        lambda f: f.update(size=0),
    ],
    ids=["dotdot", "absolute", "drive", "backslash", "http", "host", "sha", "size"],
)
def test_catalog_rejects_unsafe_entries(mutate):
    data = catalog_dict()
    mutate(data["assets"][0]["files"][0])
    with pytest.raises(ValidationError):
        Catalog.model_validate(data)


def test_catalog_rejects_non_cc0():
    with pytest.raises(ValidationError):
        Catalog.model_validate(catalog_dict(license="CC-BY"))


def test_fetch_downloads_and_verifies(tmp_path):
    catalog = Catalog.model_validate(catalog_dict())
    report = fetch_assets(catalog, tmp_path, download=FakeDownload())
    assert report.failed == [] and len(report.downloaded) == 2
    asset = catalog.get("demo_tex")
    for f in asset.files:
        assert cached_path(tmp_path, asset, f).read_bytes() == BLOBS[f.url]
    assert verify_cached(tmp_path, asset) == []


def test_fetch_skips_valid_cached_file(tmp_path):
    catalog = Catalog.model_validate(catalog_dict())
    fetch_assets(catalog, tmp_path, download=FakeDownload())
    second = FakeDownload()
    report = fetch_assets(catalog, tmp_path, download=second)
    assert second.calls == [] and len(report.skipped) == 2


def test_fetch_replaces_corrupt_file(tmp_path):
    catalog = Catalog.model_validate(catalog_dict())
    fetch_assets(catalog, tmp_path, download=FakeDownload())
    asset = catalog.get("demo_tex")
    bad = cached_path(tmp_path, asset, asset.files[0])
    bad.write_bytes(b"corrupt")
    again = FakeDownload()
    report = fetch_assets(catalog, tmp_path, download=again)
    assert again.calls == [asset.files[0].url] and len(report.downloaded) == 1
    assert bad.read_bytes() == BLOBS[asset.files[0].url]


def test_fetch_rejects_wrong_checksum(tmp_path):
    catalog = Catalog.model_validate(catalog_dict())
    wrong = FakeDownload({url: b"x" * len(data) for url, data in BLOBS.items()})
    report = fetch_assets(catalog, tmp_path, download=wrong)
    assert len(report.failed) == 2 and report.downloaded == []
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_fetch_unknown_id(tmp_path):
    catalog = Catalog.model_validate(catalog_dict())
    report = fetch_assets(catalog, tmp_path, ids=["nope"], download=FakeDownload())
    assert report.failed and "nope" in report.failed[0]


def test_verify_cached_reports_missing(tmp_path):
    catalog = Catalog.model_validate(catalog_dict())
    problems = verify_cached(tmp_path, catalog.get("demo_tex"))
    assert len(problems) == 2 and all("missing" in p for p in problems)


def test_cli_assets_fetch_uses_cache_option(tmp_path, monkeypatch, capsys):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog_dict()), encoding="utf-8")
    monkeypatch.setattr("exterior_agent.assets.fetch.download_https", FakeDownload())
    cache = tmp_path / "my cache"
    code = cli.main(["assets", "fetch", "--catalog", str(path), "--cache", str(cache)])
    assert code == 0, capsys.readouterr()
    assert (cache / "demo_tex" / "demo_tex_diff_1k.jpg").is_file()


def test_doctor_reports_asset_cache(tmp_path, monkeypatch, capsys):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog_dict()), encoding="utf-8")
    monkeypatch.setenv("EXTERIOR_AGENT_CATALOG", str(path))
    monkeypatch.setenv("EXTERIOR_AGENT_ASSETS", str(tmp_path / "empty"))
    monkeypatch.delenv("EXTERIOR_AGENT_BLENDER", raising=False)
    monkeypatch.setenv("PATH", "")
    assert cli.main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["assets"]["missing_files"] == 2
    assert report["assets"]["cache"].endswith("empty")


M2C_ASSETS = {
    "beige_wall_001": "texture",
    "brick_wall_09": "texture",
    "clean_asphalt": "texture",
    "concrete_pavement_02": "texture",
    "island_tree_02": "model",
    "street_lamp_01": "model",
    "potted_plant_02": "model",
    "shrub_03": "model",
    "shrub_04": "model",
}


def test_m2c_assets_pinned():
    from exterior_agent.assets.catalog import load_catalog

    catalog = load_catalog()
    for asset_id, kind in M2C_ASSETS.items():
        asset = catalog.get(asset_id)
        assert (asset.kind, asset.license) == (kind, "CC0"), asset_id


def test_context_model_budget():
    from exterior_agent.assets.catalog import load_catalog

    catalog = load_catalog()
    models = [a for a, k in M2C_ASSETS.items() if k == "model"]
    total = sum(f.size for a in models for f in catalog.get(a).files)
    assert total <= 60 * 2**20

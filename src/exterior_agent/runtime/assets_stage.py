"""Copy the CC0 asset files a scene plan uses from the cache into the revision's materials/."""

import shutil
from pathlib import Path

from exterior_agent.assets.catalog import load_catalog
from exterior_agent.geometry.scene_plan import required_asset_files
from exterior_agent.runtime.files import atomic_write_json, sha256_file

LICENSES = "materials/LICENSES.json"


class AssetsMissing(Exception):
    pass


def stage_assets(plan: dict, cache: Path, rev_dir: Path) -> dict[str, str]:
    """Return {relative path in the revision: sha256} for every staged file (empty if none)."""
    files = required_asset_files(plan)
    if not files:
        return {}
    bad = [
        f"{asset_id}/{rel}"
        for asset_id, rel, sha in files
        if not (Path(cache) / asset_id / rel).is_file()
        or sha256_file(Path(cache) / asset_id / rel) != sha
    ]
    if bad:
        raise AssetsMissing(
            f"{len(bad)} asset file(s) missing or corrupt in {cache} (e.g. {bad[0]}); "
            "run `exterior-agent assets fetch`"
        )
    staged: dict[str, str] = {}
    for asset_id, rel, sha in files:
        target = Path(rev_dir) / "materials" / asset_id / rel
        if not (target.is_file() and sha256_file(target) == sha):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(cache) / asset_id / rel, target)
        staged[f"materials/{asset_id}/{rel}"] = sha
    write_licenses(plan, rev_dir)
    return staged


def write_licenses(plan: dict, rev_dir: Path) -> list[dict]:
    """(Re)write materials/LICENSES.json from the plan; empty list when no assets are used."""
    files = required_asset_files(plan)
    if not files:
        return []
    catalog = load_catalog()
    used: dict[str, list[dict]] = {}
    for asset_id, rel, sha in files:
        used.setdefault(asset_id, []).append({"path": rel, "sha256": sha})
    licenses = []
    for asset_id, entries in used.items():
        asset = catalog.get(asset_id)
        licenses.append(
            {
                "id": asset.id,
                "kind": asset.kind,
                "license": asset.license,
                "authors": asset.authors,
                "source_page": asset.source_page,
                "files": entries,
            }
        )
    atomic_write_json(Path(rev_dir) / LICENSES, licenses)
    return licenses

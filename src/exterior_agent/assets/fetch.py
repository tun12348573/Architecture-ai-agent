"""Download catalog assets into a local cache, verifying size and sha256."""

import os
import shutil
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from exterior_agent.assets.catalog import ALLOWED_HOSTS, Asset, AssetFile, Catalog
from exterior_agent.runtime.files import sha256_file

CACHE_ENV = "EXTERIOR_AGENT_ASSETS"
TIMEOUT_S = 60
USER_AGENT = "exterior-agent/0.1 (asset fetch)"  # Poly Haven rejects urllib's default agent


def cache_dir(explicit: str | None = None) -> Path:
    if explicit or os.environ.get(CACHE_ENV):
        return Path(explicit or os.environ[CACHE_ENV])
    if sys.platform == "win32":
        return Path(r"C:\Tools\exterior-agent-assets")
    return Path.home() / ".cache" / "exterior-agent-assets"


def cached_path(cache: Path, asset: Asset, f: AssetFile) -> Path:
    return Path(cache) / asset.id / PurePosixPath(f.path)


def _problem(path: Path, f: AssetFile) -> str | None:
    if not path.is_file():
        return "missing"
    if path.stat().st_size != f.size:
        return "wrong size"
    if sha256_file(path) != f.sha256:
        return "checksum mismatch"
    return None


def verify_cached(cache: Path, asset: Asset) -> list[str]:
    out = []
    for f in asset.files:
        problem = _problem(cached_path(cache, asset, f), f)
        if problem:
            out.append(f"{asset.id}/{f.path}: {problem}")
    return out


@dataclass
class FetchReport:
    downloaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def download_https(url: str, target: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"refusing to download {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response, open(target, "wb") as out:
        shutil.copyfileobj(response, out)


def fetch_assets(
    catalog: Catalog,
    cache: Path,
    ids: list[str] | None = None,
    download: Callable[[str, Path], None] | None = None,
) -> FetchReport:
    download = download or download_https  # resolved at call time (patchable)
    report = FetchReport()
    wanted = ids if ids is not None else [a.id for a in catalog.assets]
    for asset_id in wanted:
        try:
            asset = catalog.get(asset_id)
        except KeyError:
            report.failed.append(f"{asset_id}: not in catalog")
            continue
        for f in asset.files:
            label = f"{asset.id}/{f.path}"
            target = cached_path(cache, asset, f)
            if _problem(target, f) is None:
                report.skipped.append(label)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_name(target.name + ".part")
            try:
                download(f.url, part)
                problem = _problem(part, f)
                if problem:
                    raise ValueError(problem)
                os.replace(part, target)
                report.downloaded.append(label)
            except Exception as exc:  # report and continue with the other files
                part.unlink(missing_ok=True)
                report.failed.append(f"{label}: {exc}")
    return report

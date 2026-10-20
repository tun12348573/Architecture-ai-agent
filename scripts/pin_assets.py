"""Dev tool: pin Poly Haven CC0 assets into assets/catalog.json (sha256 computed locally).

Usage (repo root, venv active):
  python scripts/pin_assets.py <asset_id>:<texture|hdri|model>:<resolution> ...
  e.g. painted_plaster_wall:texture:1k kloofendal_48d_partly_cloudy_puresky:hdri:2k
Each file is downloaded once, checked against Poly Haven's md5, then hashed with sha256.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

API = "https://api.polyhaven.com"
CATALOG = Path(__file__).resolve().parents[1] / "assets" / "catalog.json"
HEADERS = {
    "User-Agent": "exterior-agent/0.1 (asset pinning; github.com/tun12348573/Architecture-ai-agent)"
}
TEXTURE_MAPS = {"Diffuse": "base_color", "Rough": "roughness", "nor_gl": "normal"}


def _file(path: str, meta: dict, role: str) -> dict:
    return {
        "path": path,
        "url": meta["url"],
        "size": meta["size"],
        "md5": meta["md5"],
        "role": role,
    }


def entry_from_api(asset_id: str, info: dict, files: dict, kind: str, resolution: str) -> dict:
    if kind == "texture":
        out = []
        for key, role in TEXTURE_MAPS.items():
            meta = files[key][resolution]["jpg"]
            out.append(_file(meta["url"].rsplit("/", 1)[1], meta, role))
        dims = info.get("dimensions")
        scale = round(dims[0] / 1000, 3) if dims else 1.0
    elif kind == "hdri":
        meta = files["hdri"][resolution]["hdr"]
        out, scale = [_file(meta["url"].rsplit("/", 1)[1], meta, "hdri")], None
    elif kind == "model":
        main = files["gltf"][resolution]["gltf"]
        out = [_file(main["url"].rsplit("/", 1)[1], main, "gltf")]
        out += [_file(path, meta, "include") for path, meta in main.get("include", {}).items()]
        scale = None
    else:
        raise ValueError(f"unknown kind {kind!r}")
    return {
        "id": asset_id,
        "kind": kind,
        "license": "CC0",
        "authors": sorted(info.get("authors", {})),
        "source_page": f"https://polyhaven.com/a/{asset_id}",
        "resolution": resolution,
        "scale_m": scale,
        "files": out,
    }


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
        return json.load(r)


def _hash_download(url: str) -> tuple[str, str, int]:
    md5, sha = hashlib.md5(), hashlib.sha256()
    size = 0
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as r:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            md5.update(chunk)
            sha.update(chunk)
            size += len(chunk)
    return md5.hexdigest(), sha.hexdigest(), size


def pin(spec: str) -> dict:
    asset_id, kind, resolution = spec.split(":")
    info = _get_json(f"{API}/info/{asset_id}")
    files = _get_json(f"{API}/files/{asset_id}")
    entry = entry_from_api(asset_id, info, files, kind, resolution)
    for f in entry["files"]:
        md5, sha, size = _hash_download(f["url"])
        if md5 != f.pop("md5") or size != f["size"]:
            raise SystemExit(f"{asset_id}/{f['path']}: download does not match Poly Haven md5/size")
        f["sha256"] = sha
    return entry


def main(specs: list[str]) -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {a["id"]: a for a in catalog["assets"]}
    for spec in specs:
        entry = pin(spec)
        by_id[entry["id"]] = entry
        print(f"pinned {entry['id']} ({len(entry['files'])} files)")
    catalog["assets"] = [by_id[k] for k in sorted(by_id)]
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main(sys.argv[1:])

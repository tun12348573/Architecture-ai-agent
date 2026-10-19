"""Artifact validation, labelled contact sheet and checksummed delivery manifest."""

import json
import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat, UnidentifiedImageError

from exterior_agent.runtime.files import atomic_write_json, sha256_file

MIN_STDDEV = 2.0  # below this the image is effectively a single colour
LABEL_HEIGHT = 28
SHEET_COLUMNS = 5
GLB_MAGIC = b"glTF"
GLB_JSON_CHUNK = 0x4E4F534A
MANIFEST = "delivery.json"
EXCLUDED_FROM_MANIFEST = {MANIFEST, "job.json"}  # job.json keeps changing after packaging


def validate_png(path: Path, width: int, height: int) -> str | None:
    try:
        with Image.open(path) as img:
            if img.format != "PNG":
                return f"{path.name}: not a PNG ({img.format})"
            if img.size != (width, height):
                return f"{path.name}: size {img.size} != expected {(width, height)}"
            if ImageStat.Stat(img.convert("L")).stddev[0] <= MIN_STDDEV:
                return f"{path.name}: image is uniform (blank render?)"
    except (OSError, UnidentifiedImageError) as exc:
        return f"{Path(path).name}: unreadable image ({exc})"
    return None


def read_glb(path: Path) -> dict:
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != GLB_MAGIC:
        raise ValueError(f"{Path(path).name}: not a GLB file")
    _magic, version, length = struct.unpack_from("<4sII", data, 0)
    if version != 2 or length != len(data):
        raise ValueError(f"{Path(path).name}: unsupported GLB version or truncated file")
    chunk_len, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != GLB_JSON_CHUNK:
        raise ValueError(f"{Path(path).name}: first GLB chunk is not JSON")
    return json.loads(data[20 : 20 + chunk_len])


def validate_glb(path: Path, required_nodes: set[str], required_materials: set[str]) -> list[str]:
    try:
        doc = read_glb(path)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    nodes = {n.get("name") for n in doc.get("nodes", [])}
    materials = {m.get("name") for m in doc.get("materials", [])}
    errors = [f"GLB missing node {n}" for n in sorted(required_nodes - nodes)]
    errors += [f"GLB missing material {m}" for m in sorted(required_materials - materials)]
    return errors


def make_contact_sheet(
    images: list[tuple[str, Path]], out: Path, thumb: tuple[int, int] = (384, 216)
) -> None:
    rows = math.ceil(len(images) / SHEET_COLUMNS)
    cell_w, cell_h = thumb[0], thumb[1] + LABEL_HEIGHT
    sheet = Image.new("RGB", (SHEET_COLUMNS * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    for i, (label, path) in enumerate(images):
        x, y = (i % SHEET_COLUMNS) * cell_w, (i // SHEET_COLUMNS) * cell_h
        with Image.open(path) as img:
            sheet.paste(img.convert("RGB").resize(thumb), (x, y))
        draw.text((x + 8, y + thumb[1] + 4), label, fill="black", font=font)
    sheet.save(out, "PNG")


def write_delivery(rev_dir: Path, info: dict) -> dict:
    rev_dir = Path(rev_dir)
    files = [
        {
            "path": p.relative_to(rev_dir).as_posix(),
            "size": p.stat().st_size,
            "sha256": sha256_file(p),
        }
        for p in sorted(rev_dir.rglob("*"))
        if p.is_file() and p.relative_to(rev_dir).as_posix() not in EXCLUDED_FROM_MANIFEST
    ]
    manifest = {**info, "files": files}
    atomic_write_json(rev_dir / MANIFEST, manifest)
    return manifest


def verify_delivery(rev_dir: Path) -> list[str]:
    rev_dir = Path(rev_dir)
    try:
        manifest = json.loads((rev_dir / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{MANIFEST}: unreadable ({exc})"]
    errors = []
    for entry in manifest.get("files", []):
        path = rev_dir / entry["path"]
        if not path.is_file():
            errors.append(f"missing {entry['path']}")
        elif sha256_file(path) != entry["sha256"]:
            errors.append(f"checksum mismatch {entry['path']}")
    return errors

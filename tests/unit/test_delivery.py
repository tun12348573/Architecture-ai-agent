import json
import random
import struct
from pathlib import Path

import pytest
from PIL import Image

from exterior_agent.runtime.delivery import (
    LABEL_HEIGHT,
    make_contact_sheet,
    read_glb,
    validate_glb,
    validate_png,
    verify_delivery,
    write_delivery,
)
from exterior_agent.runtime.files import atomic_write_json, canonical_json, sha256_file


def noisy_png(path: Path, size=(128, 72), seed=1) -> Path:
    rng = random.Random(seed)
    img = Image.new("RGB", size)
    img.putdata([(rng.randrange(256),) * 3 for _ in range(size[0] * size[1])])
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


def minimal_glb(path: Path, nodes: list[str], materials: list[str]) -> Path:
    doc = {
        "asset": {"version": "2.0"},
        "nodes": [{"name": n} for n in nodes],
        "materials": [{"name": m} for m in materials],
    }
    chunk = json.dumps(doc).encode()
    chunk += b" " * (-len(chunk) % 4)
    body = struct.pack("<II", len(chunk), 0x4E4F534A) + chunk
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)
    return path


def test_valid_png_passes(tmp_path):
    assert validate_png(noisy_png(tmp_path / "a.png"), 128, 72) is None


def test_png_wrong_size(tmp_path):
    assert "size" in validate_png(noisy_png(tmp_path / "a.png"), 1280, 720)


def test_png_uniform_rejected(tmp_path):
    path = tmp_path / "flat.png"
    Image.new("RGB", (128, 72), (40, 40, 40)).save(path)
    assert "uniform" in validate_png(path, 128, 72)


def test_png_not_an_image(tmp_path):
    path = tmp_path / "x.png"
    path.write_text("not a png")
    assert validate_png(path, 128, 72) is not None
    assert validate_png(tmp_path / "missing.png", 128, 72) is not None


def test_glb_parsed_and_validated(tmp_path):
    glb = minimal_glb(tmp_path / "m.glb", ["Wall_Front"], ["MAT_Wall"])
    assert read_glb(glb)["nodes"][0]["name"] == "Wall_Front"
    assert validate_glb(glb, {"Wall_Front"}, {"MAT_Wall"}) == []
    errors = validate_glb(glb, {"Wall_Front", "Roof_Slab"}, {"MAT_Wall"})
    assert any("Roof_Slab" in e for e in errors)


def test_glb_bad_magic(tmp_path):
    path = tmp_path / "bad.glb"
    path.write_bytes(b"NOPE" + b"\0" * 32)
    with pytest.raises(ValueError):
        read_glb(path)
    assert validate_glb(path, set(), set()) != []


def test_contact_sheet_grid(tmp_path):
    images = [(f"{i:02d}_view", noisy_png(tmp_path / f"{i}.png", seed=i)) for i in range(1, 11)]
    out = tmp_path / "sheet.png"
    make_contact_sheet(images, out)
    with Image.open(out) as sheet:
        assert sheet.size == (5 * 384, 2 * (216 + LABEL_HEIGHT))


def test_delivery_checksums_detect_tampering(tmp_path):
    rev = tmp_path / "rev"
    noisy_png(rev / "images" / "01_front.png")
    (rev / "model.glb").write_bytes(b"glb")
    atomic_write_json(rev / "job.json", {"status": "running"})
    manifest = write_delivery(rev, {"complete": True})
    paths = {f["path"] for f in manifest["files"]}
    assert paths == {"images/01_front.png", "model.glb"}
    assert json.loads((rev / "delivery.json").read_text(encoding="utf-8"))["complete"] is True
    assert verify_delivery(rev) == []
    with open(rev / "model.glb", "ab") as f:
        f.write(b"!")
    assert any("model.glb" in e for e in verify_delivery(rev))
    (rev / "images" / "01_front.png").unlink()
    assert any("01_front.png" in e for e in verify_delivery(rev))


def test_file_helpers(tmp_path):
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'
    atomic_write_json(tmp_path / "x.json", {"k": "v"})
    assert json.loads((tmp_path / "x.json").read_text(encoding="utf-8")) == {"k": "v"}
    assert not list(tmp_path.glob("*.tmp"))
    assert len(sha256_file(tmp_path / "x.json")) == 64

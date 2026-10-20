import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "pin_assets", Path(__file__).resolve().parents[2] / "scripts" / "pin_assets.py"
)
pin_assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pin_assets)

PH = "https://dl.polyhaven.org/file/ph-assets"


def f(url, size=10, md5="0" * 32):
    return {"url": url, "size": size, "md5": md5}


TEX_INFO = {"authors": {"Dario Barresi": "Processing", "Charlotte Baglioni": "Photography"},
            "dimensions": [2710.0, 2710.0]}  # fmt: skip
TEX_FILES = {
    "Diffuse": {"1k": {"jpg": f(f"{PH}/Textures/jpg/1k/cw/cw_diff_1k.jpg")}},
    "Rough": {"1k": {"jpg": f(f"{PH}/Textures/jpg/1k/cw/cw_rough_1k.jpg")}},
    "nor_gl": {"1k": {"jpg": f(f"{PH}/Textures/jpg/1k/cw/cw_nor_gl_1k.jpg")}},
    "nor_dx": {"1k": {"jpg": f(f"{PH}/Textures/jpg/1k/cw/cw_nor_dx_1k.jpg")}},
}
HDRI_FILES = {"hdri": {"2k": {"hdr": f(f"{PH}/HDRIs/hdr/2k/sky_2k.hdr")}}}
MODEL_FILES = {
    "gltf": {
        "1k": {
            "gltf": {
                **f(f"{PH}/Models/gltf/1k/shrub/shrub_1k.gltf"),
                "include": {
                    "shrub.bin": f(f"{PH}/Models/gltf/1k/shrub/shrub.bin"),
                    "textures/shrub_diff_1k.jpg": f(f"{PH}/Models/jpg/1k/shrub/shrub_diff_1k.jpg"),
                },
            }
        }
    }
}


def test_texture_entry():
    e = pin_assets.entry_from_api("cw", TEX_INFO, TEX_FILES, "texture", "1k")
    roles = {x["role"]: x for x in e["files"]}
    assert set(roles) == {"base_color", "roughness", "normal"}
    assert roles["normal"]["path"] == "cw_nor_gl_1k.jpg"
    assert e["scale_m"] == 2.71 and e["license"] == "CC0"
    assert e["authors"] == ["Charlotte Baglioni", "Dario Barresi"]
    assert e["source_page"] == "https://polyhaven.com/a/cw"


def test_hdri_entry():
    e = pin_assets.entry_from_api("sky", {"authors": {"A": "All"}}, HDRI_FILES, "hdri", "2k")
    assert [(x["role"], x["path"]) for x in e["files"]] == [("hdri", "sky_2k.hdr")]
    assert e["scale_m"] is None


def test_model_entry_keeps_relative_includes():
    e = pin_assets.entry_from_api("shrub", {"authors": {"A": "All"}}, MODEL_FILES, "model", "1k")
    paths = {x["path"]: x["role"] for x in e["files"]}
    assert paths == {
        "shrub_1k.gltf": "gltf",
        "shrub.bin": "include",
        "textures/shrub_diff_1k.jpg": "include",
    }

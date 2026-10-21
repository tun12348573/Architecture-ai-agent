"""Dev tool: (re)generate examples/neoclassical_townhouse/project.json from the M2d spec §5.

Shares site, world, street context and materials with the modern demo so both demos sit in the
same street. Run from the repo root: python scripts/make_classic_fixture.py
"""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = "docs/superpowers/specs/2026-10-20-m2d-neoclassical-design.md §5"


def P(value, unit=None):
    return {"value": value, "unit": unit, "source": "m2d_spec_proposal", "source_ref": REF,
            "status": "needs_review"}  # fmt: skip


def L(v):
    return P(v, "m")


def C(v):
    return P(v, "count")


def opening(id_, kind, offset, width, height, sill, head="flat", balcony=None, **flags):
    o = {"id": id_, "kind": kind, "head": head, "offset": L(offset), "width": L(width),
         "height": L(height), "sill": L(sill)}  # fmt: skip
    if balcony:
        kind_b, projection = balcony
        o["balcony"] = {"kind": kind_b, "projection": L(projection), "rail_height": L(1.0)}
    for k, v in flags.items():
        o[k] = P(v)
    return o


def material(color, roughness, texture=None, **extra):
    v = {"base_color": color, "roughness": roughness, **extra}
    if texture:
        v["texture"] = texture
    return P(v)


def main() -> None:
    modern = json.loads(
        (ROOT / "examples/modern_townhouse/project.json").read_text(encoding="utf-8")
    )
    site = copy.deepcopy(modern["site"])
    site["front_setback"] = L(4.0)
    context = copy.deepcopy(modern["context"])
    context["pots"] = P(False)
    yard = copy.deepcopy(modern["modern"]["front_yard"])
    yard["kind"] = P("garden")
    yard["gate_piers"] = P(True)
    materials = copy.deepcopy(modern["materials"])
    materials.update(
        {
            "wall": material([0.95, 0.94, 0.91], 0.6, "painted_plaster_wall"),
            "trim": material([0.97, 0.96, 0.94], 0.45),
            "panel": material([0.88, 0.80, 0.66], 0.55, "painted_plaster_wall"),
            "roof_tiles": material([1.0, 1.0, 1.0], 0.75, "clay_roof_tiles"),
            "iron": material([0.02, 0.02, 0.02], 0.35, metallic=0.7),
            "door_wood": material([0.55, 0.32, 0.18], 0.5, "oak_wood_planks"),
            "frame": material([0.03, 0.03, 0.035], 0.4),
        }
    )
    floors = [
        {"height": L(3.6), "openings_front": [
            opening("D1", "door_wood", 0.4, 1.8, 3.0, 0.0, head="arch"),
        ], "openings_rear": [
            opening("D2", "door", 0.4, 0.9, 2.2, 0.0),
            opening("W1", "window", 2.6, 1.2, 1.4, 0.9),
        ]},
        {"height": L(3.4), "openings_front": [
            opening("D3", "door", 0.5, 1.4, 2.6, 0.0, head="arch"),
            opening("W2", "window", 3.2, 1.2, 1.8, 0.6, balcony=("balustrade", 0.45), hood=True),
        ], "openings_rear": [
            opening("W3", "window", 1.0, 1.2, 1.5, 0.9),
            opening("W4", "window", 3.0, 1.2, 1.5, 0.9),
        ]},
        {"height": L(3.4), "openings_front": [
            opening("W5", "window", 0.6, 1.2, 1.6, 1.25, balcony=("iron_straight", 0.3), hood=True),
            opening("W6", "window", 3.25, 1.1, 2.4, 0.3, head="arch", balcony=("round_iron", 0.6)),
        ], "openings_rear": [
            opening("W7", "window", 1.0, 1.2, 1.5, 0.9),
            opening("W8", "window", 3.0, 1.2, 1.5, 0.9),
        ]},
    ]  # fmt: skip
    classic = {
        "footprint_width": L(5.0),
        "footprint_depth": L(14.5),
        "wall_thickness": L(0.2),
        "slab_thickness": L(0.2),
        "floors": floors,
        "bay": {
            "side": P("left"), "width": L(2.6), "projection": L(0.9),
            "from_floor": C(2), "to_floor": C(2), "columns": P(True), "column_radius": L(0.18),
            "pediment": {"height": L(1.2), "ornament": P(True)},
        },
        "pilasters": {"width": L(0.4), "depth": L(0.08)},
        "cornices": {"height": L(0.32), "depth": L(0.28), "dentils": P(True)},
        "roof": {
            "pitch_deg": P(40.0), "overhang": L(0.4), "thickness": L(0.15),
            "gable_front": {"oculus_radius": L(0.45), "ornament": P(True)}, "gutters": P(True),
        },
        "front_yard": yard,
    }  # fmt: skip
    project = {
        "schema_version": "1.1",
        "project_id": "neoclassical-townhouse",
        "project_revision": 1,
        "input_mode": "parameters",
        "template": "neoclassical_townhouse",
        "label": "DEMO FIXTURE — neoclassical townhouse (style C), not a real building",
        "site": site,
        "classic": classic,
        "context": context,
        "materials": materials,
        "render_profile": modern["render_profile"],
        "world": modern["world"],
    }
    out = ROOT / "examples/neoclassical_townhouse/project.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(project, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                   newline="\n")  # fmt: skip
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

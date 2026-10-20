# M2d Neoclassical Townhouse (Style C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `neoclassical_townhouse` template: asymmetric facade with a projecting bay (loggia + leaf-capital columns + small ornamented pediment), real arched/round openings, mouldings with dentils, pilasters, iron/baluster balconies, procedural ornaments, and a full-length clay-tile gable roof — reusing the shared townhouse core, the M2c street context and the whole render/delivery pipeline.

**Architecture:**
- **Pure-Python core.** New pure-Python geometry turns parameters into `PlanObject`s:
  - Primitives: lathe, profile sweep, leaf, tube.
  - A prism-with-polygon-holes wall builder.
  - Massing modules (walls, slabs, roof, bay).
  - Facade modules (ornaments).
- **No booleans.** Blender only builds what `scene_plan.json` lists; no Blender boolean anywhere.
- **Template-agnostic shared code.** Site, context, interior backdrops and cameras read the common fields through `Project.body`, which is `modern` or `classic`.

**Tech Stack:** Python 3.13, Pydantic 2, Blender 5.2.2 (`bpy`), Poly Haven CC0 (`clay_roof_tiles`), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-20-m2d-neoclassical-design.md` (approved 2026-10-20).
**Reference spike (throwaway, not to be copied verbatim):** scratchpad `spike_classic/spike_classic.py`; renders in `output\spike-classic\`. The ornament proportions there are the minimum detail level the owner accepted.

## Global Constraints

- **Language:** communicate in Vietnamese; English identifiers in code.
- **Machine limits:** one Blender process at a time; no paid services.
- **Backward compatibility:** M1 golden hashes (`tests/unit/test_modern_plan.py::GOLDEN`) unchanged. The modern fixture's smoke plan hash is unchanged by this milestone (pinned in Task 2 before any refactor).
- **No booleans in the core:** every opening is a real hole built in Python (ray-castable); ornaments are deterministic (no RNG, or a fixed seed).
- **Named objects:** one object per named component (e.g. `Bay_Columns`, `Gable_Front_Ornament`), never thousands of loose parts.
- **Budget:**
  - ≤ 400 000 triangles for the main house including ornaments.
  - Final render ≤ 40 s/image, VRAM ≤ 3.5 GB.
  - Over budget → reduce ornament resolution, never drop components.
- **Bounds:** everything inside the lot; bay and balconies never pass the front boundary; roof eaves inside the lot's side lines; total height including ridge ≤ 25 m; roof pitch 25–55°.
- **Fixture provenance:** new fixture values use `"source": "m2d_spec_proposal"`, `"source_ref": "docs/superpowers/specs/2026-10-20-m2d-neoclassical-design.md §5"`, `"status": "needs_review"`.

## Review Focus

1. Arched opening whose arch radius (width/2) is ≥ its height, or whose crown + lintel exceeds the clear height → validation issue, not a triangulation crash. Test in Task 2.
2. Bay on the **right** side (the fixture is left) must mirror correctly: columns, pediment and loggia openings on the right. Test in Task 5.
3. Steep 55° pitch on a wide lot: ridge ≤ 25 m total, the gable oculus still inside the gable, neighbours never intersect the roof. Test in Task 5.
4. A classic project with `context.pots: true` → no crash and no pots (this template has no slab balconies for pots yet). Test in Task 7.
5. A polygon hole touching the wall edge (door with sill 0) or two holes 0.1 m apart → watertight wall, correct area. Test in Task 4.

---

### Task 1: Pin clay roof tiles

**Files:**
- Modify: `assets/catalog.json` (script only)
- Test: `tests/unit/test_assets.py`

**Interfaces:**
- Produces: catalog id `clay_roof_tiles` (texture 1k).

- [ ] **Step 1:** Add `"clay_roof_tiles": "texture"` to a new `M2D_ASSETS` dict. Add `test_m2d_assets_pinned`, mirroring `test_m2c_assets_pinned`.
- [ ] **Step 2:** `pytest tests/unit/test_assets.py -q` → FAIL (KeyError).
- [ ] **Step 3:** `python scripts/pin_assets.py clay_roof_tiles:texture:1k`, then `exterior-agent assets fetch`.
- [ ] **Step 4:** PASS. `doctor` reports 0 missing.
- [ ] **Step 5:** Commit `feat(assets): pin clay roof tiles`.

### Task 2: Schema, validation, fixture, `Project.body`

**Files:**
- Create: `src/exterior_agent/domain/classic.py`, `src/exterior_agent/domain/classic_rules.py`, `examples/neoclassical_townhouse/project.json`
- Modify:
  - `src/exterior_agent/domain/project.py`: `template` literal, `classic` field, `body` property, material roles.
  - `src/exterior_agent/domain/params.py`: `MaterialSpec.metallic`.
  - `src/exterior_agent/domain/validate.py`: template dispatch.
  - `src/exterior_agent/domain/modern.py`: `FrontYard.gate_piers`.
- Test: `tests/unit/test_classic_schema.py` (new), `tests/unit/conftest.py` (`classic_data` fixture), `tests/unit/test_modern_plan.py` (`MODERN_SMOKE_GOLDEN`)

**Interfaces — produces:**
- `classic.py` (all `Strict`, values are `Param`s as in `modern.py`):
  - `ClassicBalcony(kind: Literal["iron_belly", "balustrade", "round_iron", "iron_straight"], projection: Length, rail_height: Length)`
  - `ClassicOpening(id, kind: Literal["door", "window", "door_wood"], head: Literal["flat", "arch"] = "flat", offset, width, height, sill, balcony: ClassicBalcony | None = None, hood: Flag | None = None, keystone: Flag | None = None)`. `height` is sill-to-crown. An arch has radius `width / 2` and springs at `sill + height − width / 2`.
  - `ClassicFloor(height, openings_front: list[ClassicOpening] = [], openings_rear: ... = [])`
  - `Pediment(height: Length, ornament: Flag)`
  - `Bay(side: Choice, width, projection, from_floor: Count, to_floor: Count, columns: Flag, column_radius: Length, pediment: Pediment | None = None)`. `side` is `left | right`; the bay's x-range starts at its side edge of the footprint.
  - `Pilasters(width, depth)`
  - `Cornices(height, depth, dentils: Flag)`
  - `GableFront(oculus_radius: Length, ornament: Flag)`
  - `ClassicRoof(pitch_deg: Scalar, overhang: Length, thickness: Length, gable_front: GableFront, gutters: Flag)`
  - `ClassicBuilding(footprint_width, footprint_depth, wall_thickness, slab_thickness, floors: list[ClassicFloor], bay: Bay | None = None, pilasters: Pilasters | None = None, cornices: Cornices, roof: ClassicRoof, front_yard: FrontYard)`
- `FrontYard.gate_piers: Flag | None = None` (modern ignores it).
- `MaterialSpec.metallic: float = Field(0.0, ge=0, le=1)`.
- `Materials` new optional roles: `trim`, `panel`, `roof_tiles`, `iron`, `door_wood`.
- `Project.template: Literal["basic_house", "modern_townhouse", "neoclassical_townhouse"]`; `Project.classic: ClassicBuilding | None = None`; `Project.body` property (the modern or the classic block, else `None`).
- `classic_rules.check_classic(p) -> list[ValidationIssue]`. Paths start with `classic.`. Required roles: `wall`, `window_glass`, `frame`, `trim`, `panel`, `roof_tiles`, `iron`, `door_wood`, `paving`, `grass`.
- `classic_rules.ridge_height(m) -> float` (sum of floor heights + (W/2)·tan(pitch) + roof thickness).

- [ ] **Step 1: Pin modern behaviour first.** Add `MODERN_SMOKE_GOLDEN = "<sha256>"` and `test_modern_plan_hash_unchanged`. Compute the value from the current `main` code with the modern fixture and the smoke profile, and paste the literal. PASS now; it guards Tasks 5–8.
- [ ] **Step 2: Write the fixture** `examples/neoclassical_townhouse/project.json`. It uses the spec §5 values and the M2c `context` block, with `pots: false`. Field values:
  - **Floors:** 3.6 / 3.4 / 3.4 m.
  - **Openings:**
    - Floor 1 front: `door_wood`, arch, offset 0.4, width 1.8, height 3.0.
    - Floor 2 front:
      - Arched door in the loggia: offset 0.5, width 1.4, height 2.6.
      - Right flat window: offset 3.2, width 1.2, height 1.8, sill 0.6, balcony balustrade, projection 0.45.
    - Floor 3 front:
      - Left flat door: offset 0.6, width 1.2, height 2.0, sill 1.3 (sits above the pediment top), balcony iron_straight, projection 0.3.
      - Right arch window: offset 3.25, width 1.1, height 2.4, sill 0.3, balcony round_iron, projection 0.6.
    - Rear: one flat door and one window per floor.
  - **Bay:** left, width 2.6, projection 0.9, floors 2–2, columns true, radius 0.18, pediment height 1.2 with ornament.
  - **Pilasters:** 0.4 × 0.08.
  - **Cornices:** 0.32 high, 0.28 deep, dentils on.
  - **Roof:** pitch 40, overhang 0.4, thickness 0.15, oculus 0.45 with ornament, gutters on.
  - **Front yard:** `kind: garden`, `gate_piers: true`.
  - **Materials:**
    - `trim` [0.97, 0.96, 0.94]; `panel` [0.88, 0.80, 0.66] with `painted_plaster_wall`; `wall` white `painted_plaster_wall`.
    - `roof_tiles` `clay_roof_tiles`; `iron` [0.02, 0.02, 0.02], metallic 0.7, roughness 0.35.
    - `door_wood` `oak_wood_planks` tinted [0.55, 0.32, 0.18]; `frame` [0.03, 0.03, 0.035].
    - Glass with transmission 1.
- [ ] **Step 3: Write failing tests** `tests/unit/test_classic_schema.py`, each editing `classic_data`:
  - `test_fixture_parses`: template, 3 floors, `p.body is p.classic`.
  - `test_body_is_modern_for_modern(modern_data)`.
  - `test_classic_needs_classic_block`: classic template with a `modern` block → `template` issue.
  - `test_arch_taller_than_opening`: width 1.4, height 0.6 → issue `classic.floors[1].openings_front[0].height`. (Review Focus 1)
  - `test_arch_crown_above_clear_height`: floor-2 arch height 3.3 → same path.
  - `test_pitch_range`: 60 → `classic.roof.pitch_deg`; 20 → same.
  - `test_ridge_limit`: 4 floors × 6 m → `classic.floors` ("25 m").
  - `test_bay_side_choice`: `"middle"` → `classic.bay.side`.
  - `test_bay_past_front_boundary`: projection 4.5 > front setback 4.0 → `classic.bay.projection`.
  - `test_opening_hits_column`: loggia door overlapping a column x-range → `classic.floors[1].openings_front[0]`.
  - `test_oculus_outside_gable`: radius 2.0 → `classic.roof.gable_front.oculus_radius`.
  - `test_pediment_hits_opening_above`: pediment 2.0 m, floor-3 left sill 1.3 → `classic.bay.pediment.height`.
  - `test_required_roles`: delete `roof_tiles` → `materials.roof_tiles`.
  - `test_metallic_bounds`: 1.5 → pydantic error at `...metallic`.
- [ ] **Step 4:** `pytest tests/unit/test_classic_schema.py -q` → FAIL.
- [ ] **Step 5: Implement.**
  - `validate.py`: a `neoclassical_townhouse` branch, mirroring modern (needs schema 1.1, a `classic` block, no `modern`/`building`), then `check_classic` + `check_context` + `check_assets`.
  - Make `check_context` / `check_assets` read `p.body`. Their modern behaviour must not change.
  - `_zero_allowed` also allows `classic.floors…sill/offset`.
  - Column x-ranges for the overlap rule: the bay's two outer edges inset by `column_radius + 0.05`.
- [ ] **Step 6:** New tests PASS; full unit suite and both goldens PASS.
- [ ] **Step 7:** Commit `feat(domain): neoclassical townhouse schema, rules and demo fixture`.

### Task 3: Ornament primitives

**Files:**
- Create: `src/exterior_agent/geometry/classic_primitives.py`
- Test: `tests/unit/test_classic_primitives.py`

**Interfaces — produces** (all return `Mesh`, deterministic):
- `lathe(profile: list[tuple[float, float]], center: Vec3, segments: int = 32, a0: float = 0.0, a1: float = 2π) -> Mesh` — `(r, z)` revolved about the vertical through `center`; caps where `r == 0`.
- `sweep(path: list[tuple[float, float]], profile: list[tuple[float, float]], base_y: float = 0.0, closed: bool = False) -> Mesh`:
  - Profile `(d, h)` is swept along an XZ path. `d` goes towards −Y (out of the wall); `h` follows the in-plane normal `(−t_z, t_x)`.
  - Open ends are capped.
- `tube(points: list[Vec3], radius: float, sides: int = 8) -> Mesh` — closed, capped.
- `leaf(origin, up, out, side, length, width, curl, thickness=0.012) -> Mesh`:
  - Closed two-sided leaf: the spike's serrated/cupped shape plus an offset copy, with the rims stitched.
- `spiral(center: Vec3, plane_u: Vec3, plane_v: Vec3, r0, r1, turns, start, steps=80) -> list[Vec3]`.
- `merge(meshes: list[Mesh]) -> Mesh`: re-export `primitives.merge_meshes`.

- [ ] **Step 1: Write failing tests:**
  - `test_lathe_closed_and_bounds`: baluster profile from the spike → every edge used by exactly 2 faces; bounds radius = max r ± 1e-9; height = profile span.
  - `test_lathe_partial_has_flat_ends`: a0=π, a1=2π → all vertices have y ≤ center.y + 1e-9.
  - `test_sweep_straight_cornice_extent`: path (−1, 0)→(1, 0) with the spike CORNICE → x ∈ [−1, 1], y ∈ [−0.28, 0], z ∈ [0, 0.32]; closed.
  - `test_sweep_arch_outward`: semicircle path clockwise over the top → every profile point lies at radius ≥ r − 1e-9 (outward).
  - `test_tube_closed`.
  - `test_leaf_closed_and_deterministic`: two calls equal; closed.
  - `test_spiral_radius_monotonic`.
- [ ] **Step 2:** Run → FAIL (module missing).
- [ ] **Step 3: Implement.** The closedness check helper lives in `tests/unit/geom_helpers.py` as `edge_use_counts(mesh) -> Counter`.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(geometry): lathe, sweep, tube and leaf primitives`.

### Task 4: Walls and plates with polygon holes

**Files:**
- Create: `src/exterior_agent/geometry/polygon_wall.py`
- Test: `tests/unit/test_polygon_wall.py`

**Interfaces — produces:**
- `arch_outline(u0, u1, z0, z1, segments=24) -> list[tuple[float, float]]` — counter-clockwise. The semicircle crown is at `z1`; the arch springs at `z1 − (u1 − u0)/2`.
- `circle_outline(cu, cz, r, segments=32) -> list[...]`.
- `rect_outline(u0, u1, z0, z1)`.
- `prism_with_holes(outer: list[(u, z)], holes: list[list[(u, z)]], thickness: float, frame: WallFrame) -> Mesh`:
  - A closed solid: front and back faces are triangulated (ear clipping, with holes bridged into the outer ring), and reveal quads line every hole.
  - Holes may touch the bottom edge of `outer` (door sills): the touching hole is merged into the outer outline first.

- [ ] **Step 1: Write failing tests:**
  - `test_area_rect_minus_arches`: a 5 × 3.4 wall with two arch holes → front-face area = 17 − holes ± 1e-6.
  - `test_no_face_inside_hole`: no front-face triangle centroid lies inside any hole.
  - `test_watertight`: every edge is used by 2 faces.
  - `test_door_touching_sill`: rect hole u 0.4–2.2, z 0–3.0 (arched) → watertight, area correct. (Review Focus 5)
  - `test_close_holes`: holes 0.1 m apart → watertight.
  - `test_triangle_with_circle_hole`: gable outline with an oculus.
  - `test_deterministic`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** Ear clipping in pure Python; bridge each hole from its rightmost vertex to the nearest visible outer vertex, in order of decreasing max-u.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(geometry): prism walls with polygon holes`.

### Task 5: Classic massing — walls, slabs, bay, roof, gables, backdrops

**Files:**
- Create: `src/exterior_agent/geometry/classic_massing.py`
- Modify: `src/exterior_agent/geometry/modern_massing.py`: `floor_front_y` treats a missing `front_setback` as 0 and reads `p.body`.
- Test: `tests/unit/test_classic_massing.py`

**Interfaces — produces:**
- `classic_massing_objects(p) -> list[PlanObject]`. Names:
  - `Floor{n}_Wall_{Front|Rear|Left|Right}` (front/rear via `prism_with_holes`, sides via `wall_mesh`).
  - `Opening_{id}` empties (as modern).
  - `Floor{n}_Slab`.
  - `Bay_Slab_F{n}` and `Bay_Wall_F{n}` (enclosed bay floors only).
  - `Roof_Tiles_L`, `Roof_Tiles_R`, `Gable_Front`, `Gable_Rear`, `Gutter_L`, `Gutter_R`.
  - `Backdrop_{id}` (when the glass transmits; same rule as `modern_interior`).
- **Roof:** ridge along +Y at x = 0. Eaves at x = ±W/2 (inside the lot). The roof spans y ∈ [front face − overhang, rear face + overhang] at the top of the last floor. Plate thickness `roof.thickness`. Gables are triangles on the front and rear wall planes; `Gable_Front` has the oculus hole (`circle_outline`) at 40 % of the gable height.
- **Bay:**
  - Opening rule: an opening whose x-range lies within the bay goes on the main facade on the loggia floor (`from_floor`) and on the bay front wall on enclosed floors.
  - The loggia floor gets only a slab and no front wall.
- **Materials:** walls `MAT_Wall`, gables `MAT_Panel`, roof `MAT_Roof_Tiles`, gutters `MAT_Trim`, slabs `MAT_Trim`.

- [ ] **Step 1: Write failing tests:**
  - `test_expected_names(classic_data)`.
  - `test_arched_holes_real`: no `Floor2_Wall_Front` face centroid inside the floor-2 arch outline.
  - `test_roof_pitch_and_cover`: rise / (W/2) = tan(40°) ± 1e-6; y-extent = footprint ± overhang; x within the lot.
  - `test_gable_oculus_hole`.
  - `test_bay_inside_lot` and `test_bay_right_mirrors`: side right → the bay x-range lies at +x; loggia door hole on the main facade. (Review Focus 2)
  - `test_steep_roof_limits`: pitch 55, 3 floors, W 8 → ridge ≤ 25; oculus inside the gable. (Review Focus 3)
  - `test_classic_geometry_checks_clean`: `check_classic_geometry(p) == []` (Task 7 wires it; here the call goes through the shared checker, extended for `Gable_*`/`Roof_*` the same way as Cladding).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS. Full suite and goldens PASS.
- [ ] **Step 5:** Commit `feat(geometry): neoclassical massing with arched openings and clay-tile gable roof`.

### Task 6: Classic facade — mouldings, columns, balconies, ornaments

**Files:**
- Create: `src/exterior_agent/geometry/classic_facade.py`
- Test: `tests/unit/test_classic_facade.py`

**Interfaces — produces:** `classic_facade_objects(p) -> list[PlanObject]`. One object per component:
- **Mouldings:**
  - `Cornice_F{n}` (string course at each floor top; the last one is the eaves cornice), `Dentils_Roof`, `Cornice_Rake_Front`.
  - `Pilaster_L`, `Pilaster_R` (shaft + base + capital + rosette merged).
- **Openings:**
  - `Archivolt_{id}` + `Keystone_{id}` (arched openings; keystone when the flag is set or the head is an arch).
  - `Hood_{id}`.
  - `Window_{id}_Frame`, `Window_{id}_Glass` (arched glass from `arch_outline`).
  - `Door_{id}` (wood panels), `Door_{id}_Fanlight_Glass` + `_Frame` for arched `door_wood`.
- **Balconies:**
  - `Balcony_{id}_Slab`.
  - `Balcony_{id}_Iron` (`iron_belly`: semicircular bellied bars; `round_iron`: half disc on a curved corbel; `iron_straight`: straight bars with scrolls).
  - `Balcony_{id}_Balusters` (balustrade: lathe balusters + handrail + pedestals).
- **Bay:**
  - `Bay_Columns` (plinths, entasis shafts, leaf capitals, volutes, abaci).
  - `Bay_Pediment` (triangular, with a raking sweep) and `Bay_Pediment_Ornament` (scrolls + leaf fan, as the spike gable).
  - The bay balcony is `Balcony_Bay_Iron` (iron_belly in front of the columns).
- **Gable:** `Oculus_Front_Frame`, `Oculus_Front_Glass`, `Gable_Front_Ornament` (ring, C-scrolls, crown leaf fan).
- **Materials:** `MAT_Trim`, `MAT_Iron`, `MAT_Frame`, `MAT_Glass`, `MAT_Door_Wood`, `MAT_Panel`.

- [ ] **Step 1: Write failing tests:**
  - `test_component_names(classic_data)` — the exact set for the fixture.
  - `test_all_inside_lot`.
  - `test_ornaments_touch_wall`: every ornament object's max y ≥ its host wall face y − 0.01 (no floating).
  - `test_openings_unobstructed`: no ornament or column mesh vertex lies inside an opening's prism (u/z inside the outline and y between the wall faces).
  - `test_deterministic`.
  - `test_triangle_budget`: the sum of triangles over all classic objects ≤ 400 000.
  - `test_toggles`: `dentils false` → no `Dentils_Roof`; `pediment null` → no `Bay_Pediment*`; `columns false` → no `Bay_Columns`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Profiles (`CORNICE`, `STRING`, `ARCHIVOLT`, `BALUSTER`, `SHAFT`, `BELL`) are copied from the spike as module constants.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(geometry): neoclassical mouldings, columns, balconies and ornaments`.

### Task 7: Scene plan, site and context for the classic template

**Files:**
- Modify:
  - `geometry/scene_plan.py`: dispatch, `CLASSIC_MATERIALS`, bounds, `metallic`.
  - `geometry/modern_site.py`: read `p.body`; `gate_piers` → `Gate_Pier_L/R` with lathe lanterns, `MAT_Trim` + `MAT_Iron`.
  - `geometry/context.py`, `geometry/context_assets.py`: `p.body`; pots only for modern.
  - `geometry/modern_checks.py`: `check_classic_geometry(p)`.
  - `domain/validate.py`: call it.
- Test: `tests/unit/test_classic_plan.py`

**Interfaces — produces:**
- `build_scene_plan` handles `neoclassical_townhouse`. Objects = classic massing + facade + site + context + backdrops. Materials are emitted only when used.
- `classic_bounds(p) -> (building, site)`: building collections include `Roof` and `Bay`.
- A material dict gains `"metallic"` only when > 0.

- [ ] **Step 1: Write failing tests:**
  - `test_classic_plan_builds_smoke_and_preview`: preview has textures for `MAT_Roof_Tiles`.
  - `test_every_material_used` and `test_no_unknown_material`.
  - `test_cameras_fit_roof`: the ridge top is inside the building bounds.
  - `test_metallic_only_when_set`: the M1 plan has no `metallic` key.
  - `test_classic_pots_ignored`: `context.pots: true` → no `Pot_*`. (Review Focus 4)
  - `test_modern_plan_hash_unchanged` and `test_m1_plan_hash_unchanged` still pass.
  - `test_gate_piers`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS. Full suite PASS.
- [ ] **Step 5:** Commit `feat(scene): neoclassical template in the scene plan`.

### Task 8: Blender build and integration

**Files:**
- Modify:
  - `blender/scripts/build_scene.py`: `metallic`.
  - `blender/scripts/inspect_scene.py`: report `Metallic`.
- Test: `tests/integration/test_classic_scene.py` (new)

- [ ] **Step 1: Write failing integration tests.** Smoke profile; module-scoped build of the classic fixture.
  - `test_classic_build_completes`: 10 PNGs at 128 × 72; `verify_delivery == []`.
  - `test_named_components_present`: `Bay_Columns`, `Gable_Front_Ornament`, `Roof_Tiles_L`, `Balcony_Bay_Iron`, `Cornice_F3`.
  - `test_arched_openings_raycast`: rays through the floor-2 arch centre and the oculus centre miss the wall; 5 cm beside them hits (same pattern as `_wall_rays`).
  - `test_glb_reimport`: object names and `MAT_Iron` metallic ≥ 0.6.
  - `test_textured_roof_tiles` (skips without cache): `materials/clay_roof_tiles/` + `LICENSES.json`.
- [ ] **Step 2:** Run with `EXTERIOR_AGENT_BLENDER` set → FAIL (metallic not applied / missing objects).
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS. The whole integration suite passes.
- [ ] **Step 5:** Commit `feat(blender): build neoclassical scenes`.

### Task 9: Docs, real render, benchmark (manual)

- [ ] **Step 1:** README:
  - The template, the `classic` block fields, and how to choose the bay side.
  - Ornament detail level; that the roof is a full-length clay-tile gable.
  - The exact build command.
- [ ] **Step 2:** `exterior-agent benchmark "examples\neoclassical_townhouse\project.json" --samples 128`. Gate: ≤ 40 s/image, ≤ 3.5 GB VRAM, no failure. If it fails, lower `segments`/leaf counts and re-measure.
- [ ] **Step 3:** `exterior-agent build "examples\neoclassical_townhouse\project.json" --profile final`. Check `01_front`, `05_front_left` and `10_aerial` by eye against the owner's reference photo: bay + columns + pediment, arched openings, iron balconies, gable with oculus, clay roof.
- [ ] **Step 4:** STATUS gets the M2d section: measurements, revision path, manual checks, limitations. Commit `docs: M2d neoclassical template`.
- [ ] **Step 5:** Final whole-branch review → `superpowers:finishing-a-development-branch`.

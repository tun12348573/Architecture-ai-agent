# M2c Street Context, Materials and Entrance Door Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `modern_townhouse` final images read as a real Vietnamese street: clear glass + dark frames, painted walls, ground-floor brick cladding, textured road/sidewalk, deterministic neighbour townhouses, street trees/lamps, pots and a denser roof garden, no car.

**Architecture:** All new geometry stays pure Python (`geometry/modern_cladding.py`, `geometry/context.py`) emitted into `scene_plan.json`; glTF models (trees, lamps, pots, shrubs) are plan `assets` placed by the existing `add_plant`, now importing each model once and linking duplicates. Context objects live in collection `Context`, excluded from camera bounds and lot checks.

**Tech Stack:** Python 3.13, Pydantic 2, Blender 5.2.2 (`bpy`), Poly Haven CC0 assets, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-20-m2c-street-context-design.md` (approved 2026-10-20).

## Global Constraints

- Communicate in Vietnamese; English identifiers in code.
- One Blender process at a time; machine-wide lock unchanged.
- CC0 assets only, pinned with sha256 via `scripts/pin_assets.py`; models 1k; new glTF total ≤ ~60 MiB.
- Projects without `context`/`cladding`/`transmission` keep their scene plan: M1 golden hashes in `tests/unit/test_modern_plan.py::GOLDEN` must not change.
- Context is deterministic (own `random.Random(seed)`, no global state) and never enters the lot `x ∈ [−W/2, W/2], y ∈ [0, site.depth]`.
- Cameras fit building + lot only; `Context` collection never changes camera poses.
- `smoke` profile: flat colours, no assets; context meshes still present.
- Performance gate (manual, Task 9): VRAM peak ≤ 3.5 GB, no OOM, ≤ 40 s/image at 128 samples.
- New fixture values use `"source": "m2c_spec_proposal"`, `"source_ref": "docs/superpowers/specs/2026-10-20-m2c-street-context-design.md §8"`, `"status": "needs_review"`.

## Review Focus

1. Context materials unused by the scene (e.g. `per_side: 0`) must not be emitted. Otherwise `validate_glb` fails because the GLB drops unused materials. Test in Task 5.
2. Cladding top below an opening head (low canopy): validation must reject with a clear message, not crash in `wall_mesh`. Test in Task 2.
3. Narrow lot (site width 3.5 m) with neighbours: neighbours stay ≥ `NEIGHBOUR_GAP` outside the lot, with no coplanar faces against the main house side walls. Test in Task 5.
4. A `context` block on a `basic_house` project is rejected, not silently ignored. Test in Task 2.
5. Street trees and lamps never stand in front of the lot (|x| < W/2 + 1 m), where they would hide the facade in `01_front`. Test in Task 6.

---

### Task 1: Pin new CC0 assets

**Files:**
- Modify: `assets/catalog.json` (via script only)
- Test: `tests/unit/test_assets.py`

**Interfaces:**
- Produces: catalog ids `beige_wall_001`, `brick_wall_09`, `clean_asphalt`, `concrete_pavement_02` (texture 1k); `island_tree_02`, `street_lamp_01`, `potted_plant_02`, `shrub_03`, `shrub_04` (model 1k).

- [ ] **Step 1: Write failing test** `test_m2c_assets_pinned`: each id above exists with the listed `kind`, `license == "CC0"`. Also `test_context_model_budget`: the summed `size` of every file of `island_tree_02`, `street_lamp_01`, `potted_plant_02`, `shrub_03` and `shrub_04` is ≤ 60 × 2**20.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/unit/test_assets.py -q` → FAIL (ids missing).
- [ ] **Step 3:** `python scripts/pin_assets.py beige_wall_001:texture:1k brick_wall_09:texture:1k clean_asphalt:texture:1k concrete_pavement_02:texture:1k island_tree_02:model:1k street_lamp_01:model:1k potted_plant_02:model:1k shrub_03:model:1k shrub_04:model:1k`, then `exterior-agent assets fetch`.
- [ ] **Step 4:** Tests PASS; `exterior-agent doctor` reports 0 missing asset files.
- [ ] **Step 5:** Commit `feat(assets): pin M2c CC0 textures and models`.

### Task 2: Schema — transmission, cladding, street context

**Files:**
- Modify: `src/exterior_agent/domain/params.py` (`MaterialSpec`)
- Modify: `src/exterior_agent/domain/modern.py`
- Modify: `src/exterior_agent/domain/project.py` (`Materials`, `Project`)
- Modify: `src/exterior_agent/domain/modern_rules.py`
- Modify: `src/exterior_agent/domain/validate.py`
- Test: `tests/unit/test_context_schema.py` (new)

**Interfaces:**
- Produces:
  - `MaterialSpec.transmission: float = Field(default=0.0, ge=0, le=1)`.
  - New `Materials` optional roles: `cladding`, `asphalt`, `sidewalk`, `kerb`, `road_marking`, `neighbour_wall`, `neighbour_glass`.
  - In `modern.py`:
    - `Cladding(zone: Choice, thickness: Length)`.
    - `Neighbours(per_side: Count, seed: Count)`.
    - `ContextModels(tree: Choice, lamp: Choice, pot: Choice)`.
    - `StreetContext(front: Choice, sidewalk_width: Length, road_width: Length, neighbours: Neighbours | None = None, street_lamps: Flag, street_trees: Flag, pots: Flag, models: ContextModels)`.
  - `ModernBuilding.cladding: Cladding | None = None`.
  - `Project.context: StreetContext | None = None`.
  - `modern_rules.check_context(p) -> list[ValidationIssue]`, called from `check_modern`.

- [ ] **Step 1: Write failing tests** (build each case by editing `modern_data`):
  - `test_context_requires_modern`: put `context` on `demo_data`, then `validate_project` → an issue with path `template`.
  - `test_front_choice`: `front.value = "river"` → issue `context.front` ("road or park").
  - `test_per_side_range`: 5 → issue `context.neighbours.per_side` ("0..4").
  - `test_context_roles_required`: delete `materials.asphalt` → issue `materials.asphalt`. Delete `materials.neighbour_wall` while `neighbours` is set → issue.
  - `test_cladding_zone_and_role`: `zone="rear"` → issue `modern.cladding.zone`. With no `materials.cladding` → issue.
  - `test_context_models_kind`: `models.tree = "concrete"` → issue (kind texture ≠ model), via `check_assets`.
  - `test_transmission_bounds`: 1.5 → pydantic error.
  - `test_cladding_below_opening_head`: canopy height 2.5 with a door top at 2.6 + transom → issue `modern.cladding` ("cladding top … below opening").
- [ ] **Step 2:** `pytest tests/unit/test_context_schema.py -q` → FAIL.
- [ ] **Step 3: Implement.**
  - Context roles required when `context` is set: `CONTEXT_MATERIAL_ROLES = ("asphalt", "sidewalk", "kerb", "road_marking", "neighbour_glass")`. Add `neighbour_wall` when `neighbours` is set; `cladding` when `modern.cladding` is set.
  - Cladding top = `min(canopy.height, floors[0].height)` when a canopy exists, else `floors[0].height`. Every floor-1 front opening top must be ≤ top − `MIN_LINTEL`.
  - In `validate.py`, the basic_house branch rejects `p.context is not None` with the existing template message style.
- [ ] **Step 4:** New tests PASS; the full unit suite passes and `GOLDEN` is unchanged.
- [ ] **Step 5:** Commit `feat(domain): street context, cladding and glass transmission schema`.

### Task 3: Glass transmission and darker, thicker door frames

**Files:**
- Modify: `src/exterior_agent/geometry/scene_plan.py` (`_material`)
- Modify: `src/exterior_agent/geometry/modern_facade.py` (`PROFILE` per kind)
- Modify: `src/exterior_agent/blender/scripts/build_scene.py` (`make_material`)
- Modify: `src/exterior_agent/blender/scripts/inspect_scene.py` (`material_inputs`)
- Modify: `examples/modern_townhouse/project.json`:
  - `window_glass`: `{base_color [0.92, 0.96, 0.94], roughness 0.02, alpha 1.0, transmission 1.0}`.
  - `aluminium`: `base_color [0.06, 0.06, 0.06]`.
  - `wall`: `texture beige_wall_001`, `base_color [1, 1, 1]`.
- Test: `tests/unit/test_modern_facade.py`, `tests/unit/test_scene_plan.py`, `tests/integration/test_modern_scene.py`

**Interfaces:**
- Produces:
  - A plan material dict gains `"transmission": float` **only when > 0**.
  - `modern_facade.PROFILES = {"door_4leaf": 0.08, "window": 0.06}`.
  - `inspect_scene` `material_inputs` adds `"transmission": float`, read from the Principled socket `"Transmission Weight"`.

- [ ] **Step 1: Write failing tests:**
  - `test_door_4leaf_profile_is_80mm`: stile width of `Door_D1_Frame` is 0.08 ± 0.001.
  - `test_transmission_only_when_set`: the fixture plan's `MAT_Glass` has `transmission == 1.0`; the M1 demo plan has no `"transmission"` key.
  - Integration `test_glass_transmits` (smoke build): inspect shows `MAT_Glass` transmission 1.0, and the GLB `extensionsUsed` contains `"KHR_materials_transmission"`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** In `make_material`, when `spec.get("transmission", 0) > 0`, set `"Transmission Weight"` to the value and `"IOR"` to 1.45, and skip the alpha/BLENDED branch.
- [ ] **Step 4:** PASS. Run the integration with `EXTERIOR_AGENT_BLENDER` set. `GOLDEN` is unchanged.
- [ ] **Step 5:** Commit `feat(render): clear transmissive glass, dark 80 mm door frames, painted walls`.

### Task 4: Ground-floor brick cladding

**Files:**
- Create: `src/exterior_agent/geometry/modern_cladding.py`
- Modify: `src/exterior_agent/geometry/scene_plan.py`:
  - `_modern_plan_objects` appends `cladding_objects(p)`.
  - `MODERN_MATERIALS["MAT_Cladding"] = "cladding"`.
- Modify: `src/exterior_agent/geometry/modern_checks.py` (include cladding objects in the checked list)
- Modify: `examples/modern_townhouse/project.json`:
  - `modern.cladding = {zone: "ground_front", thickness: 0.02 m}`.
  - `materials.cladding = {texture: brick_wall_09, base_color [1, 1, 1], roughness 0.85}`.
- Test: `tests/unit/test_modern_cladding.py` (new)

**Interfaces:**
- Produces: `cladding_objects(p) -> list[PlanObject]`. It returns `[PlanObject("Cladding_F1_Front", "Facade", mesh, "MAT_Cladding")]`, or `[]` when `modern.cladding is None`.
  - Mesh: `wall_mesh(w, z_top, thickness, holes)` placed on `WallFrame((−W/2, yf − thickness, 0), (1,0,0), (0,1,0), W, 0.0)`.
  - `yf = floor_front_y(p, 1)`.
  - `holes` are the floor-1 front openings, using the same `u0`/`z` as `_floor_objects`.
  - `z_top` follows the Task 2 rule.

- [ ] **Step 1: Write failing tests:**
  - `test_cladding_bounds`: x ∈ [−W/2, W/2] ± 1 mm; y ∈ [yf − 0.02, yf]; z ∈ [0, z_top].
  - `test_cladding_has_opening_holes`: no cladding face centroid falls inside any floor-1 front opening rectangle (u, z), ± 1 mm.
  - `test_no_cladding_when_absent`: `cladding = None` → `[]`, and the plan has no `MAT_Cladding`.
  - `test_cladding_passes_geometry_checks`: `check_modern_geometry(fixture) == []`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `cladding_objects`.
- [ ] **Step 4:** PASS. Full unit suite passes.
- [ ] **Step 5:** Commit `feat(geometry): ground-floor front brick cladding`.

### Task 5: Street context geometry (road/park, sidewalk, kerb, neighbours)

**Files:**
- Create: `src/exterior_agent/geometry/context.py`
- Modify: `src/exterior_agent/geometry/scene_plan.py`:
  - `_modern_objects_and_materials` appends `context_objects(p)`.
  - Emit neighbour materials.
  - `MODERN_MATERIALS` gains `MAT_Asphalt`, `MAT_Sidewalk`, `MAT_Kerb`, `MAT_Road_Marking`, `MAT_Neighbour_Glass`.
- Modify: `src/exterior_agent/geometry/modern_site.py`: when `p.context` is set, `Site_Context` sits at z = `−KERB_HEIGHT − 0.01`.
- Modify: `examples/modern_townhouse/project.json`:
  - `context`: road; sidewalk 3 m; road 7 m; neighbours `per_side 2, seed 7`; lamps, trees and pots on; models `island_tree_02` / `street_lamp_01` / `potted_plant_02`.
  - Context materials: `asphalt` (clean_asphalt), `sidewalk` (concrete_pavement_02), `kerb` (concrete), `road_marking` (flat `[0.9, 0.9, 0.85]`), `neighbour_wall` (beige_wall_001), `neighbour_glass` (flat dark `[0.05, 0.06, 0.07]`, roughness 0.05); `context_ground` gains `texture leafy_grass` (far ground no longer flat grey).
  - `front_yard.car = false`, `motorbikes = 0`.
- Test: `tests/unit/test_context.py` (new)

**Interfaces:**
- Produces in `geometry/context.py`:
  - Constants `KERB_HEIGHT = 0.15`, `NEIGHBOUR_GAP = 0.02`, `NEIGHBOUR_FLOOR_HEIGHT = 3.3`, `STREET_HALF_LENGTH = 30.0`.
  - `NEIGHBOUR_TINTS: tuple[tuple[float, float, float], ...]`: 5 entries, multiplied onto `neighbour_wall.base_color`.
  - `@dataclass(frozen=True) NeighbourSpec(name: str, x0: float, x1: float, y0: float, y1: float, floors: int, tint: int)`.
  - `neighbour_specs(p) -> list[NeighbourSpec]`:
    - Names `Neighbour_L{k}` / `Neighbour_R{k}`; `k = 1` is adjacent to the lot.
    - Width 4–6 m; front setback y0 ∈ [0, 3]; depth = footprint_depth ± 2 m; floors 2–5.
    - Drawn from `random.Random(seed)` in a fixed order L1..Ln, then R1..Rn.
  - `context_objects(p) -> list[PlanObject]`, all in collection `"Context"`. Objects:
    - `Sidewalk_Front` (top z=0), `Kerb_Front`.
    - `road`: `Road`, `Road_Marking` (one merged mesh of dashes 3 m long, 3 m gap, 0.15 m wide, z = −KERB_HEIGHT + 0.005), `Sidewalk_Opposite`.
    - `park`: `Road` (lane), `Park_Lawn` (`MAT_Grass`).
    - Per neighbour: `Neighbour_X` (`MAT_Neighbour_{tint+1}`) and `Neighbour_X_Glass` (window panes inset 0.1 m on the front face, one per floor, `MAT_Neighbour_Glass`) — the "simple balcony" is the inset; no extra slab [plan call: keeps parts count low].
    - The street spans x ∈ [−STREET_HALF_LENGTH, STREET_HALF_LENGTH].

- [ ] **Step 1: Write failing tests:**
  - `test_context_outside_lot`: every Context mesh bound is outside the lot interior (either y ≤ 0 + 1e-9, or |x| ≥ W/2 + NEIGHBOUR_GAP − 1e-9). Run it for the fixture and for a 3.5 m-wide lot variant.
  - `test_neighbours_deterministic`: same seed → identical specs; seed 8 → at least one different `floors`.
  - `test_neighbour_ranges`: widths 4–6, floors 2–5, y0 0–3, adjacent ones touch (x1 of L1 == x0 of L2 ± 1e-9) and don't overlap.
  - `test_road_vs_park_parts`: road → `{"Road", "Road_Marking", "Sidewalk_Opposite"}` ⊂ names and no `Park_Lawn`; park → `Park_Lawn` present, no `Road_Marking`.
  - `test_cameras_ignore_context`: camera poses with `context` == poses with `context = None`.
  - `test_unused_context_materials_not_emitted`: `per_side 0` → no `MAT_Neighbour_*` in plan materials, and every plan material is used by some object.
  - `test_no_car_in_fixture`: the plan has no `Prop_*` objects. Update `test_modern_plan.EXPECTED` accordingly (drop Prop_*, add Context/Cladding names).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `context.py` and the scene_plan wiring. Neighbour materials are emitted only for tints actually used.
- [ ] **Step 4:** PASS. Full unit suite passes; `GOLDEN` is unchanged.
- [ ] **Step 5:** Commit `feat(geometry): street context with road/park, sidewalk and neighbour townhouses`.

### Task 6: Asset placements — roof garden, pots, street trees, lamps

**Files:**
- Modify: `src/exterior_agent/geometry/modern_massing.py` (`PLANT_SPACING = 0.8`)
- Create: `src/exterior_agent/geometry/context_assets.py`
- Modify: `src/exterior_agent/geometry/scene_plan.py`: `_world_and_plants` builds `assets` from roof plants + `context_asset_specs(p)`.
- Modify: `src/exterior_agent/domain/modern_rules.py` (`check_assets` covers `context.models.*`)
- Modify: `examples/modern_townhouse/project.json`: `garden.plant_models = [shrub_01, shrub_02, shrub_03, shrub_04]`.
- Test: `tests/unit/test_context_assets.py` (new), `tests/unit/test_textured_plan.py`

**Interfaces:**
- Produces: `context_asset_specs(p) -> list[AssetPlacement]` with `@dataclass(frozen=True) AssetPlacement(name: str, collection: str, model: str, location: tuple[float, float, float], rotation_z: float, scale: float)`.
  - Pots: `Pot_F{n}_{k}` in collection `"Plants"`, 2 per balcony and 2 per terrace. Position 0.35 m inside the balcony slab corners at the rail side; on terraces, 0.5 m in from the side walls and 0.4 m behind the rail.
  - Trees: `Tree_{k}` in `"Context"`.
    - `road`: on the sidewalk at y = −sidewalk_width + 0.8, x every 8 m from ±(W/2 + 3), skipping |x| < W/2 + 1.
    - `park`: grid on the lawn, jittered from `random.Random(seed)`.
  - Yard tree: when `front_yard.kind == "garden"` and `street_trees` is set, one `Tree_Yard` in `"Context"` at (−W/2 + 1.0, front_setback / 2, 0), so it stands beside, not in front of, the entrance.
  - Lamps: `Lamp_{k}` in `"Context"`, y = −sidewalk_width + 0.4, x = ±(W/2 + 7) then every 20 m.
  - Scale: trees 0.85–1.15 from the same seeded RNG; pots and lamps 1.0. `rotation_z = k * PLANT_TURN`.
  - Trees/lamps only when the matching flag is set and `neighbours`' seed exists (seed default 0 when neighbours is null).
- `_world_and_plants` maps each placement to the existing plan asset dict (`model`, `includes`, `location`, `rotation_z`, `scale`).

- [ ] **Step 1: Write failing tests:**
  - `test_pots_on_slabs`: every pot (x, y) lies on its balcony/terrace floor with a 0.3 m margin, z = slab top.
  - `test_trees_and_lamps_clear_of_lot_front`: every tree/lamp has |x| ≥ W/2 + 1 and y < 0.
  - `test_assets_deterministic`: two calls → equal lists.
  - `test_yard_tree_only_for_garden`: `parking` → no `Tree_Yard`; `garden` → one `Tree_Yard` inside the front yard, ≥ 0.5 m from the gate opening.
  - `test_roof_garden_denser`: the fixture has `round(inner / 0.8)` roof plants.
  - `test_smoke_plan_has_no_assets`: smoke plan → no `"assets"` key.
  - Update `tests/integration/test_textured_scene.py::test_plants_in_roof_planter`: expected count = `len(roof_plant_positions(project))`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS. Full unit suite passes.
- [ ] **Step 5:** Commit `feat(geometry): pots, street trees, lamps and denser roof garden`.

### Task 7: Blender — import each model once, linked duplicates

**Files:**
- Modify: `src/exterior_agent/blender/scripts/build_scene.py` (`add_plant` → `add_asset(spec, scene, base, cache: dict)`)
- Modify: `src/exterior_agent/blender/scripts/inspect_scene.py` (`object_entry` adds `"mesh": obj.data.name` for meshes)
- Test: `tests/integration/test_textured_scene.py`

**Interfaces:**
- Consumes: the plan `assets` from Task 6.
- Produces: `add_asset(spec, scene, base, cache)`.
  - The first import of a model path keeps today's behaviour: join, base-align, XY-centre.
  - Later specs do `obj = cache[path].copy()`, which shares `obj.data`, then set name/location/rotation (`rotation_mode = "XYZ"`)/scale and link into `spec["collection"]`.

- [ ] **Step 1: Write failing tests** (textured build, skipped without the asset cache):
  - `test_trees_are_linked_duplicates`: all `Tree_*` share one `mesh` name.
  - `test_tree_height_sane`: each tree's bbox height is 3–15 m.
  - `test_context_collection_present`: `Neighbour_L1`, `Road`, `Sidewalk_Front` are in `Context`.
  - `test_brick_staged_and_licensed`: `materials/brick_wall_09/` exists and `LICENSES.json` lists it.
- [ ] **Step 2:** Run → FAIL (separate meshes per tree).
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS. All textured integration tests pass, including the rotation test from M2b.
- [ ] **Step 5:** Commit `feat(blender): import each CC0 model once and link duplicates`.

### Task 8: Delivery `illustrative`, README, STATUS

**Files:**
- Modify: `src/exterior_agent/runtime/runner.py` (`package` info)
- Modify: `README.md`, `docs/STATUS.md`
- Test: `tests/unit/test_runner_assets.py`

**Interfaces:**
- Produces: `delivery.json["illustrative"] = {"note": "minh hoạ, không phải hiện trạng hay số đo", "objects": sorted(names of plan objects in collection "Context"), "assets": sorted(plan asset names)}`. Only present when either list is non-empty.

- [ ] **Step 1: Write failing test** `test_delivery_lists_illustrative`: a fake-Blender build of the fixture has `illustrative.objects ⊇ {"Road", "Neighbour_L1"}`. A plain M1 build has no `illustrative` key.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Update the README:
  - The `context` block and its fields.
  - Build a separate revision with `"neighbours": null` to see the side walls.
  - Car removed in the demo.
  - New asset list.
  - STATUS M2c section skeleton.
  - One-time revision rename (new optional fields).
- [ ] **Step 4:** PASS. Run `.\scripts\check.ps1`, then the integration suite with `EXTERIOR_AGENT_BLENDER` set → all pass.
- [ ] **Step 5:** Commit `feat(runtime): mark context and plants illustrative in delivery; docs`.

### Task 9: Real render, benchmark, visual check (manual)

- [ ] **Step 1:** `exterior-agent benchmark "examples\modern_townhouse\project.json" --samples 128` → record s/image, VRAM peak and min free RAM. Gate: VRAM ≤ 3.5 GB, ≤ 40 s/image, no failure. If the gate fails, reduce `per_side` to 1 and drop street trees to every 12 m, then re-measure.
- [ ] **Step 2:** `exterior-agent build "examples\modern_townhouse\project.json" --profile final` → open `contact_sheet.png`, `01_front.png` and `05_front_left.png`. Check:
  - Glass reads clear with a dark interior.
  - Bricks are ~0.06 × 0.24 m (±20%). If not, set `scale_m` in the catalog entry for `brick_wall_09`, with a test asserting the new value.
  - No grey plane in frame.
  - No floating or clipping plants.
- [ ] **Step 3:** If the interior reads bright or empty, add `Interior_Backdrop` panels per spec §5: a dark matte quad 1.5 m behind each front opening, in collection `Interior_Backdrop`, with a unit test on its position. Otherwise record "not needed" in STATUS.
- [ ] **Step 4:** Write measured numbers, revision path and manual-check results into `docs/STATUS.md`; commit `docs(status): M2c measured render and visual check`.
- [ ] **Step 5:** Show the owner the images; final whole-branch review; `superpowers:finishing-a-development-branch`.

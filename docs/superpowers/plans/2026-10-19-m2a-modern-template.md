# M2a Modern Townhouse Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `schema_version 1.1` projects with `template: "modern_townhouse"` build a multi-floor modern townhouse (setbacks/terraces, glass balconies, projecting frames, vertical louvers, canopy, framed 4-leaf aluminium door and windows, parapet, stair head, roof garden, front-yard fence/gate/props) with box-mapped UVs, flat materials, 10 views, `.blend`/`.glb` — while every `1.0` project produces a byte-identical scene plan.

**Architecture:** New pure-Python modules generate named meshes per component from a `ModernBuilding` model; `build_scene_plan` dispatches on `project.template`; the Blender build script gains UV support. Textures/HDRI/CC0 assets/benchmark/final GPU profile are plan **M2b** (not here).

**Tech Stack:** unchanged (Python 3.13, Pydantic 2, Blender 5.2.2, pytest).

**Spec:** `docs/superpowers/specs/2026-10-19-m2-modern-townhouse-design.md` (approved 2026-10-19). This plan covers spec §1 goals except textures/HDRI/CC0/benchmark, plus §3, §4, §7 and §8 except the asset-backed tests.

## Global Constraints

- `1.0` projects unchanged: `sha256(canonical_json(build_scene_plan(demo_house, smoke)))` == `a4b3f08d4dbdf3af336bca8db463dba0eb6797cd85f31a0e42d74b4f258b062e`; preview == `c4f2b1a127eda2d62ff3f9bfe95220e2df0191d2df1224bbe044a19b38a5865c`.
- `template` ∈ `basic_house` (default) | `modern_townhouse`; `modern_townhouse` requires `schema_version "1.1"`, a `modern` block and no `building` block; `basic_house` requires `building` and no `modern`.
- Every design number is a `Param` (`Length`/`Count`/`Choice`/new `Flag(Param[bool])`), normalized to metres. `TOL = 0.001`.
- Limits: 1–5 floors; total height (floors + parapet + stair head above roof) ≤ `MAX_TOTAL_HEIGHT = 25.0`; floor 1 `front_setback` = 0 and setbacks non-decreasing upward; `MIN_CLEAR = 2.4` (floor height − slab); M1 corner/lintel/pier rules per floor wall; `CAR_LENGTH = 4.4`, `CAR_WIDTH = 1.8`; motorbikes 0–4.
- Coordinates as M1: Z-up, front = −Y, lot x ∈ [−W/2, W/2], y ∈ [0, D]. Floor `n` front wall outer face at `y = site.front_setback + floor.front_setback`.
- Object names (distinct, each a separate object): `Floor{n}_Wall_Front|Rear|Left|Right`, `Floor{n}_Slab` (slab on top of floor n; the top floor's is the roof slab), `Floor{n}_Terrace_Rail`, `Floor{n}_Terrace_Pergola`, `Balcony_F{n}`, `Balcony_F{n}_Rail`, `Frame_F{a}-{b}`, `Louver_F{n}_{k}` (k from 1), `Canopy`, `Parapet`, `StairHead`, `Roof_Pergola`, `Planter_Roof_{k}`, `Door_{id}_Frame` + `Door_{id}_Glass` (4-leaf), `Door_{id}` (plain leaf), `Window_{id}_Frame` + `Window_{id}_Glass`, `Opening_{id}` (empty), `Yard_Front`, `Yard_Rear`, `Fence_Left`, `Fence_Right`, `Gate`, `Site_Context`, `Prop_Car`, `Prop_Motorbike_{k}`.
- Collections: `Building`, `Openings`, `Doors`, `Windows`, `Balconies`, `Facade` (frames, louvers, canopy), `Roof` (parapet, stair head, roof pergola, planters, terrace rails/pergolas), `Site`, `Props`, `Cameras`, `Lights`.
- Material roles → names: wall `MAT_Wall`, roof `MAT_Roof`, frame `MAT_Frame`, aluminium `MAT_Aluminium`, window_glass `MAT_Glass`, louver `MAT_Louver`, terrace_floor `MAT_Terrace_Floor`, paving `MAT_Paving`, grass `MAT_Grass`, soil `MAT_Soil`, pergola_wood `MAT_Pergola_Wood`, context_ground `MAT_Context_Ground`, props `MAT_Props`. M1 roles/names unchanged for `basic_house`.
- UVs: modern meshes only; box mapping in metres (1 UV unit = 1 m) chosen per face by dominant normal axis.
- Camera fitting for modern: `building` bounds = union of objects in `Building`, `Doors`, `Windows`, `Balconies`, `Facade`, `Roof`; `site` bounds = lot ∪ building.
- Fixture opening ids: `D1` (floor 1 front, `door_4leaf` 3.2 × 2.6, transom 0.5), `D2` (floor 1 rear door), `W1` (floor 1 rear window), `W2`/`W3` (floor 2 front/rear windows), `W4`/`W5` (floor 3 front/rear windows); other numbers per spec §7, the rest chosen by the implementer and marked `needs_review`.
- Commands as M0/M1: `.\scripts\check.ps1`; integration needs `EXTERIOR_AGENT_BLENDER`.

## Review Focus

1. Everything optional switched off (no balconies/frames/louvers/canopy, `garden` yard, no car, 0 motorbikes, no pergolas) → valid, closed walls, builds. Test: `test_modern_minimal_config` (Task 6).
2. One-floor modern house → roof slab directly on floor 1 with parapet and stair head; no terrace objects. Test: `test_single_floor_modern` (Task 3).
3. Five floors exactly at `MAX_TOTAL_HEIGHT` accepted; +0.002 m rejected. Tests: `test_height_limit_accepted`, `test_height_limit_rejected` (Task 1).
4. Whole modern project in `mm` → identical scene plan as metres. Test: `test_modern_mm_equals_m` (Task 6).
5. Same opening id on two floors → rejected at the second path. Test: `test_duplicate_opening_id_across_floors` (Task 1).

---

### Task 1: Schema 1.1 models and validation

**Files:**
- Modify: `src/exterior_agent/domain/project.py`, `src/exterior_agent/domain/validate.py`
- Create: `src/exterior_agent/domain/modern.py` (models), `src/exterior_agent/domain/modern_rules.py` (semantic checks), `examples/modern_townhouse/project.json` (spec §7, label "DEMO FIXTURE — modern townhouse, not a real building", proposals `needs_review`, source `m2_spec_proposal`, source_ref `docs/superpowers/specs/2026-10-19-m2-modern-townhouse-design.md §7`)
- Test: `tests/unit/test_modern_schema.py`; add fixture `modern_data() -> dict` to `tests/unit/conftest.py`

**Interfaces:**
- Produces:
  - `project.Flag(Param[bool])` (unit None; strict bool).
  - `project.Materials`: six existing required roles + optional `frame, aluminium, louver, terrace_floor, paving, grass, soil, pergola_wood, props: MaterialParam | None = None`.
  - `project.Project`: `schema_version: Literal["1.0","1.1"]`, `template: Literal["basic_house","modern_townhouse"] = "basic_house"`, `building: Building | None = None`, `modern: ModernBuilding | None = None`; pairing rule enforced in a model validator (issue path `template`).
  - `modern.py`: `ModernOpening(id, kind: Literal["door","window","door_4leaf"], offset, width, height, sill: Length, transom_height: Length | None = None)`; `Floor(height, front_setback: Length, openings_front: list[ModernOpening] = [], openings_rear: list[ModernOpening] = [], terrace_pergola: Flag | None = None)`; `Balcony(floor: Count, offset, width, depth, rail_height, slab_thickness: Length)`; `FacadeFrame(from_floor: Count, to_floor: Count, thickness, depth: Length)`; `Louvers(floor: Count, offset, width: Length, count: Count, blade_width, blade_depth: Length)`; `Canopy(height, depth, thickness: Length)`; `StairHead(width, depth, height: Length)`; `RoofGarden(planter_width, planter_height: Length, pergola: Flag)`; `ModernRoof(parapet_height, parapet_thickness: Length, stair_head: StairHead, garden: RoofGarden | None = None)`; `FrontYard(kind: Choice, gate_width, gate_height, fence_height: Length, car: Flag, motorbikes: Count)`; `ModernBuilding(footprint_width, footprint_depth, wall_thickness, slab_thickness: Length, floors: list[Floor], balconies: list[Balcony] = [], frames: list[FacadeFrame] = [], louvers: list[Louvers] = [], canopy: Canopy | None = None, roof: ModernRoof, front_yard: FrontYard)`. Floor indices 1-based.
  - `modern_rules.check_modern(p: Project) -> list[ValidationIssue]`: Global Constraints limits plus openings per floor wall (M1 rules, wall height = floor height − slab, facade length = footprint width; `door_4leaf`: sill 0 and `0 < transom_height < height`), balcony floor in 2..n and `y ≥ 0` after projection, frame floors share one setback, louvers inside facade with `count ≥ 2`, canopy z above floor-1 front opening tops and below floor-1 height, stair head inside roof, car requires `kind == "parking"` and `site.front_setback ≥ CAR_LENGTH + 0.1` (fixture 4.5 m is exactly on the limit), `gate_width ≤ site.width`, modern material roles all present, footprint/site fit as M1.
  - `validate.check_semantics` dispatches: M1 rules for `basic_house`, `check_modern` for `modern_townhouse`.

- [ ] **Step 1: Failing tests** `test_modern_schema.py`: `test_modern_fixture_is_valid` (3 floors, template modern, unresolved non-empty); `test_m1_fixture_still_valid`; `test_template_pairing_rules` (modern + `building` → issue `template`; `"1.0"` + modern → issue); `test_height_limit_accepted` / `test_height_limit_rejected` (25.0 / 25.002); `test_floor1_setback_must_be_zero`; `test_setbacks_non_decreasing`; `test_duplicate_opening_id_across_floors` (issue path `modern.floors[1].openings_front[0].id`); `test_balcony_out_of_lot_rejected`; `test_car_needs_parking_and_depth`; `test_door_4leaf_rules` (sill 0.1 → issue; transom ≥ height → issue); `test_missing_modern_material_role` (drop `materials.louver` → issue `materials.louver`).
- [ ] **Step 2:** Run `python -m pytest tests/unit/test_modern_schema.py -v` → FAIL (import error).
- [ ] **Step 3:** Implement models, pairing validator, `check_modern`, fixture.
- [ ] **Step 4:** Run `python -m pytest tests/unit -q` → all PASS (M1 tests included).
- [ ] **Step 5:** Commit `feat(domain): schema 1.1 modern townhouse model and validation`.

### Task 2: Geometry primitives — framed glazing, rails, UVs

**Files:**
- Create: `src/exterior_agent/geometry/primitives.py`
- Test: `tests/unit/test_primitives.py`

**Interfaces:**
- Consumes: `Mesh`, `MeshBuilder`, `box_mesh` (mesh.py); `WallFrame` (layout.py).
- Produces:
  - `merge_meshes(meshes: list[Mesh]) -> Mesh`.
  - `framed_glazing(frame: WallFrame, u0, u1, z0, z1, v_center: float, columns: int, transom_height: float, profile: float, depth: float) -> tuple[Mesh, Mesh]` → (merged frame members: outer rectangle, `columns − 1` mullions, transom bar when `transom_height > 0`; glass panes 0.01 m thick, one per cell).
  - `glass_rail(lo: Vec3, hi: Vec3) -> Mesh` (box).
  - `box_uvs(mesh: Mesh) -> list[list[tuple[float, float]]]` — per face per corner; dominant |normal| axis X → (y, z), Y → (x, z), Z → (x, y); metres.

- [ ] **Step 1: Failing tests:** merged counts add up and indices valid; `framed_glazing` 4 columns + transom: frame bounds == opening box (±TOL), 5 panes, panes inside the opening with zero overlap volume against every frame member; `columns=1`, no transom → 1 pane; `box_uvs` of a 2×3×4 box: the +Z face UV extent is 2×3 and the ±X faces 3×4; list length == face count and each entry length == face vertex count.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(geometry): framed glazing, rails, box UVs and mesh merge`.

### Task 3: Modern massing — floors, walls, slabs, terraces, roof

**Files:**
- Create: `src/exterior_agent/geometry/modern_massing.py`
- Test: `tests/unit/test_modern_massing.py`

**Interfaces:**
- Consumes: Task 1 models; `wall_mesh` (walls.py), `WallFrame`, `box_mesh`, `merge_meshes`.
- Produces:
  - `@dataclass(frozen=True) PlanObject(name: str, collection: str, mesh: Mesh | None, material: str | None, empty_box: tuple[Vec3, Vec3] | None = None)` (an empty when `mesh is None`).
  - `floor_base_z(m: ModernBuilding, n: int) -> float`.
  - `floor_frames(p: Project, n: int) -> dict[str, WallFrame]` (M1 conventions; front face per Global Constraints; side walls between that floor's front and rear walls; wall height = floor height − slab).
  - `massing_objects(p: Project) -> list[PlanObject]`: per floor four walls with real holes, `Opening_{id}` empties, `Floor{n}_Slab` over floor n's footprint, terrace rail (+ pergola when `terrace_pergola`) where `setback[n+1] > setback[n]` (`Floor{n}_Terrace_Rail` along the terrace front edge, glass, 1.1 m), `Parapet` (closed ring on the roof slab perimeter, inside the footprint), `StairHead` (box on the roof slab against the rear parapet, centred in x), `Planter_Roof_{k}` along the roof front, `Roof_Pergola` when `roof.garden.pergola`.

- [ ] **Step 1: Failing tests** (fixture): all `Floor{n}_Wall_*` closed; floor 3 front wall outer face at `y = 4.5 + 2.0`; floor bases 0, 3.6, 6.9; floor-1 wall top at `3.6 − slab`; terrace objects only on floor 2, rail spanning full width at `y = 4.5`; parapet 1.1 above roof slab top and closed; stair head inside the roof footprint, touching the rear parapet inner face (±TOL); each opening centre not inside its wall (`tests/unit/geom_helpers.point_inside`); `test_single_floor_modern`: no `Floor*_Terrace_*`, parapet + stair head on `Floor1_Slab`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(geometry): modern multi-floor massing with terraces and roof`.

### Task 4: Facade components — balconies, frames, louvers, canopy, doors, windows

**Files:**
- Create: `src/exterior_agent/geometry/modern_facade.py`
- Test: `tests/unit/test_modern_facade.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`PlanObject`, `floor_frames`, `floor_base_z`, `framed_glazing`, `glass_rail`).
- Produces: `facade_objects(p: Project) -> list[PlanObject]`:
  - `Balcony_F{n}`: slab whose top is at floor n's base z, projecting `depth` toward −Y from that floor's front face; `Balcony_F{n}_Rail`: glass on the front and both ends, top at slab top + `rail_height`.
  - `Frame_F{a}-{b}`: two posts + top beam + bottom beam projecting `depth` from the front face, outer edges flush with the footprint sides, spanning floors a..b.
  - `Louver_F{n}_{k}`: `count` vertical blades evenly spaced across `[offset, offset + width]`, height = floor clear height, centred `0.05 + blade_depth/2` in front of the face.
  - `Canopy`: full-width slab at `height`, projecting `depth`.
  - Openings: `door_4leaf` → `Door_{id}_Frame` (4 columns + transom) + `Door_{id}_Glass`; `window` → `Window_{id}_Frame` (2 columns) + `Window_{id}_Glass`; `door` → `Door_{id}` leaf. Materials per Global Constraints (door/window frames `MAT_Aluminium`, glass `MAT_Glass`, balcony/canopy slabs `MAT_Wall`, facade frame `MAT_Frame`, louvers `MAT_Louver`).

- [ ] **Step 1: Failing tests** (fixture): balcony floor 2 y-range `[3.5, 4.5]`, top z 3.6; rail top z 4.7; frame bars outer x = ±2.5, front face y = 4.1; louver count and even spacing; canopy y-range `[3.3, 4.5]`; `Door_D1_Frame` x/z bounds == opening box; `Door_D1_Glass` has 5 panes (5 closed box components); facade objects pairwise overlap volume ≤ 1e-9; every object within the lot (`y ≥ −TOL`, `|x| ≤ 2.5 + TOL`).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(geometry): modern facade components`.

### Task 5: Site and props — yards, fence, gate, car, motorbikes

**Files:**
- Create: `src/exterior_agent/geometry/modern_site.py`
- Test: `tests/unit/test_modern_site.py`

**Interfaces:**
- Produces: `site_objects(p: Project) -> list[PlanObject]`: `Yard_Front` (paving or grass quad over `y ∈ [0, site.front_setback]`), `Yard_Rear` (grass), `Site_Context` (as M1), `Fence_Left`/`Fence_Right` along `y = 0` either side of a centred gate gap, `Gate` (merged vertical slats) filling the gap, `Prop_Car` (merged boxes: body, cabin, 4 wheel blocks; `CAR_LENGTH × CAR_WIDTH × 1.5`, nose toward the house, centred in the front yard) when `car`, `Prop_Motorbike_{k}` (merged boxes ~1.9 × 0.7 × 1.1) beside the car. Materials: paving `MAT_Paving`, grass `MAT_Grass`, fence/gate `MAT_Aluminium`, props `MAT_Props`.

- [ ] **Step 1: Failing tests:** gate width/height and centred gap; fences + gate exactly cover the front boundary; car inside the front yard, not intersecting facade objects (balcony, canopy, frame) or the building; motorbikes inside the lot and not intersecting the car; `garden` + no car → no `Prop_*` and `Yard_Front` material `MAT_Grass`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(geometry): modern site, fence, gate and props`.

### Task 6: Scene plan dispatch, UVs, cameras, backward compatibility

**Files:**
- Modify: `src/exterior_agent/geometry/scene_plan.py`
- Test: `tests/unit/test_modern_plan.py`

**Interfaces:**
- Consumes: Tasks 3–5 object lists, `box_uvs`, `fit_cameras`.
- Produces: `build_scene_plan(project, render)` unchanged for `basic_house`; for `modern_townhouse` the same schema plus `"uvs"` on every mesh object and only referenced materials; cameras fitted per Global Constraints. `required_object_names` / `required_material_names` unchanged.

- [ ] **Step 1: Failing tests:** `test_m1_plan_hash_unchanged` (both golden hashes); `test_modern_plan_names_unique_and_expected` (set equality with the expected fixture names written in the test); every mesh has `uvs` with one entry per face; every referenced material defined; 10 cameras with all target corners in frame; `test_modern_minimal_config`; `test_modern_mm_equals_m` (canonical JSON equal after rounding floats to 1e-9).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run `python -m pytest tests/unit -q` → PASS.
- [ ] **Step 5:** Commit `feat: modern template scene plan with UVs and fitted cameras`.

### Task 7: Blender UV support and real-Blender integration

**Files:**
- Modify: `src/exterior_agent/blender/scripts/build_scene.py` (create a `UVMap` layer from `uvs` when present), `src/exterior_agent/blender/scripts/inspect_scene.py` (report `uv_layers` count per mesh)
- Test: `tests/integration/test_modern_scene.py`

**Interfaces:**
- Consumes: `run_build`, `BuildOptions`, `resolve_render("smoke")`, `inspect` helper (tests/integration/conftest.py).

- [ ] **Step 1: Failing tests** (marker `blender`): modern fixture build → completed, 10 PNGs validate, `verify_delivery == []`; reopened `.blend` has every plan object in its collection and each modern mesh has 1 UV layer; `Floor3_Wall_Front` bbox == pure-Python bounds ±TOL; ray-cast on the **wall object** through each `Opening_*` centre → no hit, through a pier → hit; GLB reimport wall/balcony bboxes ±TOL; changed parameters (no balconies, 4 floors) → new revision without `Balcony_F2` and with `Floor4_Wall_Front`.
- [ ] **Step 2:** Run `python -m pytest tests/integration/test_modern_scene.py -v` → FAIL (no UV layers). **Step 3:** Implement. **Step 4:** Run `.\scripts\check.ps1` → PASS.
- [ ] **Step 5:** Commit `feat(blender): UV layers and modern template integration tests`.

### Task 8: Docs, manual render, review

**Files:**
- Modify: `README.md` (modern template: fixture path, components, how to switch them off), `docs/STATUS.md`

- [ ] **Step 1:** `exterior-agent validate "examples\modern_townhouse\project.json"` and `exterior-agent build "examples\modern_townhouse\project.json"` (preview, flat materials) → completed; inspect `contact_sheet.png`, record the manual visual check in STATUS, show the owner.
- [ ] **Step 2:** Update README/STATUS (M2a done; M2b next: CC0 assets, textures, HDRI, final GPU profile, benchmark).
- [ ] **Step 3:** `.\scripts\check.ps1` → PASS. Commit `docs: modern template usage and M2a status`.
- [ ] **Step 4:** superpowers:requesting-code-review on the M2a range, then superpowers:verification-before-completion.

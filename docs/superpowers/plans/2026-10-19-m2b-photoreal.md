# M2b Near-Photoreal Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modern-template renders become near-photoreal: CC0 PBR textures, an HDRI sky and CC0 plant models, a `final` profile on Cycles GPU (CUDA) with denoising whose sample count is chosen by a measured `benchmark` command, and a delivery package that carries the used textures plus licences.

**Architecture:** A committed asset catalog (`assets/catalog.json`, Poly Haven CC0 files with sha256) is downloaded once into a cache outside git by `exterior-agent assets fetch`. Materials may name a texture asset; projects may name an HDRI. For non-smoke profiles the scene plan references texture/HDRI/model files under the revision's `materials/` folder, which the runner fills from the cache (checksummed) before Blender builds the scene; the `.blend` keeps relative paths. Smoke builds and every `basic_house` project stay flat and asset-free.

**Tech Stack:** unchanged (Python stdlib `urllib`/`hashlib`, Pydantic, Blender 5.2.2 Cycles/Eevee, OpenImageDenoise), Poly Haven public API (read-only, pinning time only).

**Spec:** `docs/superpowers/specs/2026-10-19-m2-modern-townhouse-design.md` §1 (assets), §5, §6, §8 (asset-backed and manual tests). M2a is merged (`main`).

## Global Constraints

- Asset licence: CC0 only, from Poly Haven (`https://dl.polyhaven.org/...`). Downloads: HTTPS only, host allowlist `{"dl.polyhaven.org"}`, size and sha256 verified, atomic rename; nothing downloaded is executed or imported by host Python.
- Catalog paths are relative POSIX paths without `..`, absolute parts or drive letters.
- Resolutions: textures `1k` or `2k`, HDRI `2k`, model textures `1k`.
- Cache dir: env `EXTERIOR_AGENT_ASSETS`, default `C:\Tools\exterior-agent-assets` on Windows and `~/.cache/exterior-agent-assets` elsewhere. Layout `<cache>/<asset_id>/<file path>`.
- Revision layout addition: `materials/<asset_id>/<file path>` (only files actually used) and `materials/LICENSES.json` (`[{id, kind, license, authors, source_page, files: [{path, sha256}]}]`).
- `basic_house` scene plans unchanged (M2a golden hashes). Modern `smoke` plans contain no texture/world/model entries and build without a cache.
- `final` profile: 1920×1080, `CYCLES`, device `GPU` (CUDA first, then OptiX), OpenImageDenoise on, samples from benchmark (initial 128, updated in Task 7). `preview`: Eevee 1280×720 with textures + HDRI. `--samples N` overrides any profile.
- Blender-side scripts: stdlib + `bpy` only; file paths stored in `.blend` are relative (`//materials/...`).
- Car/motorbikes stay placeholders (Poly Haven has no CC0 car model — spec §6 fallback), listed in `delivery.json` as `"placeholders"`.
- One Blender process at a time; benchmark renders sequentially.

## Review Focus

1. Cache missing a file, or a cached file with wrong sha256 → `preview`/`final` build fails before Blender with a message containing `exterior-agent assets fetch`; `assets fetch` re-downloads only missing/bad files. Tests: `test_build_fails_without_cached_assets` (Task 5), `test_fetch_replaces_corrupt_file` (Task 1).
2. Catalog entry with `../` path, absolute path, `http://` URL or non-allowlisted host → rejected before any download. Test: `test_catalog_rejects_unsafe_entries` (Task 1).
3. `smoke` and `basic_house` stay asset-free: golden hashes hold, modern smoke plan has no textures, smoke build succeeds with an empty cache. Tests: `test_m1_plan_hash_unchanged` (kept), `test_smoke_plan_is_flat` (Task 4), `test_smoke_build_without_cache` (Task 5).
4. A texture inside a revision's `materials/` edited after completion → `verify_delivery` reports it; an incomplete revision with an edited texture refuses to resume. Test: `test_edited_texture_detected` (Task 5).
5. GPU out-of-memory during render → stage `failed` quickly with a hint to lower samples/plants or use `--device cpu`, not a hang. Test: `test_gpu_oom_hint` (Task 5; fake Blender prints Cycles' OOM line and exits 1).

---

### Task 1: Asset catalog model, safe fetch and `assets fetch` CLI

**Files:**
- Create: `src/exterior_agent/assets/__init__.py`, `src/exterior_agent/assets/catalog.py`, `src/exterior_agent/assets/fetch.py`, `assets/catalog.json` (`{"schema": "asset_catalog/1", "assets": []}`)
- Modify: `src/exterior_agent/cli/main.py` (`assets fetch [--catalog PATH] [--cache DIR]`), `src/exterior_agent/runtime/doctor.py` (cache dir + missing file count)
- Test: `tests/unit/test_assets.py`

**Interfaces:**
- Produces:
  - `catalog.AssetFile(path: str, url: str, size: int, sha256: str, role: str)`; `catalog.Asset(id: str ^[a-z0-9_]+$, kind: Literal["texture","hdri","model"], license: Literal["CC0"], authors: list[str], source_page: str, resolution: str, scale_m: float | None, files: list[AssetFile])`; `catalog.Catalog(schema: Literal["asset_catalog/1"], assets: list[Asset])` with `get(asset_id) -> Asset` (KeyError). Pydantic `extra="forbid"`; validators enforce path safety, https + allowlisted host, 64-hex sha256, size > 0.
  - `catalog.load_catalog(path: Path | None = None) -> Catalog` (default `<repo>/assets/catalog.json` from the package location, or env `EXTERIOR_AGENT_CATALOG`).
  - `fetch.cache_dir(explicit: str | None = None) -> Path`; `fetch.cached_path(cache, asset, f) -> Path`; `fetch.verify_cached(cache, asset) -> list[str]`.
  - `fetch.fetch_assets(catalog, cache, ids: list[str] | None = None, download: Callable[[str, Path], None] = download_https) -> FetchReport(downloaded: list[str], skipped: list[str], failed: list[str])`; downloads to `<target>.part`, checks size + sha256, then `os.replace`.
  - `fetch.download_https(url, target) -> None` (urllib, 60 s timeout, re-checks scheme/host).

- [ ] **Step 1: Failing tests** (fake `download`): `test_catalog_rejects_unsafe_entries` (parametrized `../x.jpg`, `/abs.jpg`, `C:/x.jpg`, `http://dl.polyhaven.org/a`, `https://evil.example/a`, bad sha256); `test_fetch_downloads_and_verifies`; `test_fetch_skips_valid_cached_file` (download not called); `test_fetch_replaces_corrupt_file`; `test_fetch_rejects_wrong_checksum` (failed, no file and no `.part` left); `test_verify_cached_reports_missing`; `test_cli_assets_fetch_uses_cache_option`; `test_doctor_reports_asset_cache`.
- [ ] **Step 2:** Run `python -m pytest tests/unit/test_assets.py -v` → FAIL. **Step 3:** Implement. **Step 4:** Run `python -m pytest tests/unit -q` → PASS.
- [ ] **Step 5:** Commit `feat(assets): CC0 asset catalog, verified fetch and assets CLI`.

### Task 2: Pin real CC0 assets

**Files:**
- Create: `scripts/pin_assets.py`, `tests/unit/test_pin_assets.py`
- Modify: `assets/catalog.json`

**Interfaces:**
- Produces: `pin_assets.entry_from_api(asset_id: str, info: dict, files: dict, kind: str, resolution: str) -> dict` (pure: textures → JPG `Diffuse`→`base_color`, `Rough`→`roughness`, `nor_gl`→`normal`; HDRI → `hdri/<res>/hdr`; models → `gltf/<res>/gltf` plus its `include` files with their relative paths; authors = keys of `info["authors"]`; `source_page = https://polyhaven.com/a/<id>`; `scale_m` from `info["dimensions"]` mm → m when present, else 1.0). CLI `python scripts/pin_assets.py <id>:<kind>:<res> ...` downloads each file once, checks Poly Haven's md5, computes sha256, updates `assets/catalog.json`.

- [ ] **Step 1: Failing test** `test_entry_from_api` with trimmed copies of real API responses (one texture, one HDRI, one model) → expected roles, urls, paths, authors, scale.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5 (network):** Choose CC0 assets via the API: one texture each for `wall` (light plaster/paint), `frame` (dark cladding/concrete), `louver` and `pergola_wood` (wood), `paving`, `terrace_floor` (tiles), `roof` (concrete), `grass`, `soil`; one partly-cloudy daylight HDRI (2k); two small plant models (1k). Pin them, run `exterior-agent assets fetch`, record cache size; confirm each asset page states CC0.
- [ ] **Step 6:** Commit `feat(assets): pin CC0 textures, HDRI and plant models`.

### Task 3: Schema — textured materials, world, roof plants

**Files:**
- Modify: `src/exterior_agent/domain/params.py` (`MaterialSpec.texture: str | None = None`), `src/exterior_agent/domain/project.py` (`World(hdri: Choice, strength: Param[float], rotation_deg: Param[float])` with unit None; `Project.world: World | None = None`), `src/exterior_agent/domain/modern.py` (`RoofGarden.plant_models: list[str] = []`), `src/exterior_agent/domain/modern_rules.py`
- Modify: `examples/modern_townhouse/project.json` (Task 2 textures per role, `world`, roof plant models; `needs_review`)
- Test: `tests/unit/test_textured_schema.py`

**Interfaces:**
- Produces: modern-only validation — each `materials.<role>.value.texture`, `world.hdri`, `modern.roof.garden.plant_models[i]` exists in `load_catalog()` with kind `texture`/`hdri`/`model` (issue at that path); `world` or any `texture` on `basic_house` → issue `template`; `strength` in (0, 10]; `rotation_deg` in [0, 360).

- [ ] **Step 1: Failing tests:** fixture valid; unknown texture id → issue at its path; HDRI id naming a texture → issue; world on demo_house → issue; strength 0 → issue; M1 fixture still valid.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run `python -m pytest tests/unit -q` → PASS (golden hashes green).
- [ ] **Step 5:** Commit `feat(domain): textured materials, HDRI world and roof plant models`.

### Task 4: Scene plan — textures, world, plants

**Files:**
- Modify: `src/exterior_agent/geometry/scene_plan.py`, `src/exterior_agent/geometry/modern_massing.py` (plant positions along `Planter_Roof_1`)
- Test: `tests/unit/test_textured_plan.py`

**Interfaces:**
- Consumes: `load_catalog`, Task 3 schema.
- Produces: for `modern_townhouse` with profile ≠ `smoke`: material entries gain `"textures": {role: {"path": "materials/<id>/<file>", "sha256"}}` and `"texture_scale_m"`; plan gains `"world": {"hdri": {"path", "sha256"}, "strength", "rotation_deg"}` when `project.world`, and `"assets": [{"name": "Plant_Roof_{k}", "collection": "Roof", "model": {"path", "sha256"}, "includes": [{"path", "sha256"}], "location", "rotation_z", "scale"}]`. `required_asset_files(plan) -> list[tuple[str, str, str]]` (asset_id, file path, sha256), each file once. For `smoke`/`basic_house`: none of these keys.

- [ ] **Step 1: Failing tests:** golden hashes still green; `test_smoke_plan_is_flat`; `test_preview_plan_references_textures` (wall path and sha256 from catalog); `test_world_in_plan`; `test_plants_inside_planter` (locations inside the planter top face, z = planter top); `test_required_asset_files_complete`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: textured scene plan with HDRI world and plant models`.

### Task 5: Runner — stage assets, licences, failures, `--samples`

**Files:**
- Modify: `src/exterior_agent/runtime/runner.py`, `src/exterior_agent/runtime/delivery.py`, `src/exterior_agent/domain/render.py` (`resolve_render(..., samples: int | None = None)`, samples ≥ 1), `src/exterior_agent/cli/main.py` (`build --samples N`), `tests/fakes/fake_blender.py` (`FAKE_BLENDER_OOM=1` prints `System is out of GPU memory` and exits 1)
- Test: `tests/unit/test_runner_assets.py`

**Interfaces:**
- Produces: `stage_assets(plan, cache, rev_dir) -> list[str]` (copies each `required_asset_files` entry after sha256 check, writes `materials/LICENSES.json`, returns relative paths; raises `AssetsMissing(message)` naming missing ids and `exterior-agent assets fetch`); runner calls it before the build stage, maps `AssetsMissing` → `failed` without starting Blender, and records staged files' sha256 in `job.json` `artifacts` (so the existing resume rule refuses edited textures). `BuildOptions.asset_cache: Path | None = None` (None → `cache_dir()`). Render failure with `out of GPU memory` or `CUDA error` in its log → message gains `lower --samples or plants, or use --engine cycles --device cpu`. `delivery.json` gains `assets: [{id, license}]` and `placeholders`.

- [ ] **Step 1: Failing tests** (fake Blender, temp cache filled through `fetch_assets` with a fake download): `test_build_fails_without_cached_assets` (preview, empty cache → failed, message has `exterior-agent assets fetch`, no `logs/build.log`); `test_textures_staged_and_licensed`; `test_smoke_build_without_cache`; `test_edited_texture_detected`; `test_gpu_oom_hint`; `test_samples_override` (`resolve_render("final", samples=64).samples == 64`; CLI `--samples 0` → exit 2).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run `python -m pytest tests/unit -q` → PASS.
- [ ] **Step 5:** Commit `feat(runtime): stage CC0 assets with licences; GPU OOM hint; --samples`.

### Task 6: Blender — PBR materials, HDRI, plants, final profile

**Files:**
- Modify: `src/exterior_agent/blender/scripts/build_scene.py` (image textures through UV + Mapping scale `1/texture_scale_m`; roughness/normal as Non-Color, normal via Normal Map node; glass stays procedural; World = Environment Texture + Mapping rotation + strength; import each plant glTF, join into one object named per plan, place/rotate/scale, link to its collection; `bpy.ops.file.make_paths_relative()` before saving; Cycles `use_denoising=True`, `denoiser="OPENIMAGEDENOISE"` when the render dict says `denoise`), `render_views.py` (`--samples N`), `inspect_scene.py` (report `images: [{name, filepath, exists}]`, world node types), `src/exterior_agent/domain/render.py` (`final` → CYCLES GPU 128 + `denoise: True`)
- Test: `tests/integration/test_textured_scene.py` (marker `blender`; skipped with a reason when the cache lacks the fixture's assets)

**Interfaces:**
- Consumes: Tasks 3–5.

- [ ] **Step 1: Failing tests:** preview build of the modern fixture at 128×72 (replace on `RenderSettings`) completes; reopened `.blend` images have `filepath` starting `//materials/` and exist; world has an Environment Texture with the HDRI; `Plant_Roof_*` exist in `Roof` inside the planter bounds ±TOL; `MAT_Wall` has an Image Texture linked to Base Color; GLB has ≥ 1 image referenced by the wall material; after copying the revision dir elsewhere every image still resolves.
- [ ] **Step 2:** Run `python -m pytest tests/integration/test_textured_scene.py -v` (after `exterior-agent assets fetch`) → FAIL. **Step 3:** Implement, verifying each `bpy` API on Blender 5.2.2. **Step 4:** Run `.\scripts\check.ps1` → PASS.
- [ ] **Step 5:** Commit `feat(blender): PBR textures, HDRI world, plant models and final profile`.

### Task 7: Benchmark command and final sample choice

**Files:**
- Create: `src/exterior_agent/runtime/benchmark.py`
- Modify: `src/exterior_agent/cli/main.py` (`benchmark <project> [--profile final] [--samples 64,128,256,512] [--views 01_front,10_aerial] [--out output/benchmarks]`)
- Test: `tests/unit/test_benchmark.py`

**Interfaces:**
- Produces: `run_benchmark(project, render, samples: list[int], views: list[str], out: Path, blender: list[str], sampler: Callable[[], dict] = sample_resources) -> dict` — stages assets and builds the scene once, then one `render_views.py` run per level (sequential) while a thread calls `sampler()` every 0.5 s; writes `<out>/benchmark.json` (atomic) `{"blender_version", "render", "levels": [{"samples", "views": {id: seconds}, "seconds_per_view_avg", "vram_used_mib_peak", "ram_available_gb_min", "images": {id: path}}]}`. `sample_resources() -> dict` (`nvidia-smi --query-gpu=memory.used`, None if unavailable; RAM via `doctor._memory()`).

- [ ] **Step 1: Failing tests** (fake Blender + fake sampler): levels in order, each view timed, peak/min across samples, images per level, valid `benchmark.json`; bad `--samples` list → exit 2; renders never overlap (fake Blender lock file).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. Commit `feat(runtime): benchmark command with VRAM/RAM sampling`.
- [ ] **Step 5 (manual, real GPU):** `exterior-agent benchmark "examples\modern_townhouse\project.json" --samples 64,128,256,512`; record s/view, VRAM peak and RAM min in STATUS; show the owner the images per level; set `final` samples to the lowest level the owner judges good within the spec target (≤ 3 min/view); commit `chore: set final samples from benchmark`.

### Task 8: Final render, docs, review

**Files:**
- Modify: `README.md` (assets fetch, cache, licences, final/benchmark, `--samples`), `docs/STATUS.md`, `docs/dependency-policy.md` (asset pinning policy)

- [ ] **Step 1:** `exterior-agent build "examples\modern_townhouse\project.json" --profile final` → record total and per-view seconds; show the owner `contact_sheet.png`; record the manual check and feedback in STATUS.
- [ ] **Step 2:** Docs. `.\scripts\check.ps1` → PASS. Commit `docs: photoreal rendering, assets and benchmark`.
- [ ] **Step 3:** superpowers:requesting-code-review on the M2b range, then superpowers:verification-before-completion.

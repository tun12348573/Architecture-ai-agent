# Exterior AI Agent — Claude Code project instructions

Updated: 2026-10-19. Communicate with the owner in Vietnamese; use English identifiers in code.
This is a self-contained project brief for Claude Code. Implement incrementally using Superpowers.
The project is currently a design, not a working application. Inspect the actual repository before making implementation claims.

## 1. Goal and boundaries

- Build an AI assistant for exterior architectural visualization from CAD or photos/sketches/dimensions.
- Interiors remain in JEGA. Deliver consistent exterior images and editable 3D assets.
- One canonical 3D scene produces every view of a design revision. Change geometry before rerendering images.
- The owner uses Windows/PowerShell on ASUS ROG Strix G513IE_G513IE with **8 GB DDR4 RAM**. Inspect actual CPU/GPU/VRAM; the model name is not a hardware benchmark.
- Run **one Blender job/process at a time** on this laptop; render the camera set sequentially. Keep API/CI/cloud services off the laptop when introduced.
- Architectural visualization is the initial scope. Structural engineering, construction documents, estimates, JEGA automation and arbitrary photorealistic reconstruction are outside the initial release.

## 2. Superpowers workflow

- Superpowers installed in Codex does not install it in Claude Code. Verify the Claude Code plugin and available skill names before claiming to use them.
- If missing, tell the owner to run `/plugin install superpowers@claude-plugins-official` inside Claude Code, then reload/restart the session and verify. Do not silently substitute a different plugin or run a remote installer script.
- Load `superpowers:using-superpowers`; announce relevant skills briefly. These are development workflows, separate from the application's AI tools.
- Use `superpowers:brainstorming` to inspect the repository and reconcile this brief with existing code. Do not repeat questions already answered here; ask only for consequential missing information.
- Write the current milestone's spec to `docs/superpowers/specs/YYYY-MM-DD-<scope>-design.md`. Use `superpowers:writing-plans` for the corresponding small plan in `docs/superpowers/plans/`.
- Follow required spec/plan reviews in the installed skills; do not claim an unwritten plan was approved. Preserve existing approvals and execution choices rather than asking for them again.
- Default recommendation: sequential implementation with `superpowers:executing-plans`. Use `superpowers:using-git-worktrees` when isolation is needed; preserve an existing managed worktree and the owner's changes.
- Use `superpowers:test-driven-development` for functional changes, `superpowers:systematic-debugging` for failures, and `superpowers:requesting-code-review` before integration.
- Use `superpowers:receiving-code-review` to assess feedback, `superpowers:verification-before-completion` before success claims, and `superpowers:finishing-a-development-branch` when appropriate.
- Do not launch parallel implementers, agent teams or multiple render workers on this laptop by default. Use subagents only when the owner selects that approach; review their work independently.
- Complete authorized implementation and verification; a plan, scaffold, mock screenshot or list of suggestions is not a working milestone. If blocked, state the exact missing prerequisite and continue independent work.

## 3. Delivery order

Start with **M0 + M1** unless the owner requests another milestone. Plan later subsystems separately; do not scaffold every future service in the first change.

| Milestone | Deliverable and gate |
| --- | --- |
| M0 | Repository setup, dependency/version policy, config, README, local checks and real CI workflow files for existing functionality. |
| M1 | Validated parameters → simple one-storey flat-roof house → 10 preview renders → editable `.blend`, `.glb` and delivery package; no live AI dependency. |
| M2 | Tested templates for floors, balconies, roofs and materials; benchmark complexity before expansion. |
| M3 | DXF ingestion plus photo/sketch intake, provenance, unit conversion and unresolved-information review. |
| M4 | Configurable cloud AI provider, structured tool calls, human review of design assumptions and bounded execution. |
| M5 | Central API, Auth, PostgreSQL, private Storage, multi-machine workers, revision conflicts and overload protection; staging validation. |
| M6 | n8n integrations through protected APIs after the underlying tools work reliably. |

M0/M1 must run without paid services. Do not add Kubernetes, microservices, a local image model or a full Docker Desktop stack to achieve M1.
Do not provision billable resources or deploy production as a side effect of local development. Prepare reviewable configuration before any required approval.

## 4. Input and design truth

- Input **A**: 2D CAD, possibly incomplete floor plans/elevations/sections. Prefer DXF via `ezdxf`; request a DXF export for DWG and retain the original. Do not promise native DWG parsing.
- Check units, scale, layers, blocks, external references and contradictory measurements. Reading CAD lines does not automatically identify walls/doors correctly.
- Input **C**: photographs, sketches or land dimensions. Collect footprint, setbacks, floors, heights, roof, openings and constraints only as needed.
- A photograph cannot establish exact dimensions or unseen rear/side/roof geometry. Mark inferred details as proposals requiring confirmation; never fabricate measured facts.
- Every design value carries `value`, `unit`, `source`, `source_ref`, `status`; use `needs_review` / `confirmed`. Extracted values are not automatically confirmed.
- M1 uses an explicitly labelled demo fixture, not the owner's real building: land 4.5 × 18 m, footprint 4.5 × 12 m, front/rear setbacks 5/1 m, one floor, wall height 3.6 m, flat roof.
- Specify wall/roof thickness, door/window locations and dimensional tolerance in the M1 spec before coding. All fixtures must fit their site and produce actual wall openings.
- Generate revisions into new directories. Preserve source files and hand-edited `.blend` files; never overwrite manual changes during parameter regeneration.

## 5. Technology and module boundaries

- Geometry, materials, cameras and export: **Blender + Python (`bpy`)**. Select a supported Blender LTS, verify APIs against that exact release and pin the version.
- Host application: Python, Pydantic for validation, CLI first. Keep pure geometry/parameter calculations testable without importing `bpy`.
- Separate host Python dependencies from Blender's embedded Python; lock each required environment and check compatibility instead of assuming one virtualenv works everywhere.
- M1 persistence: SQLite for metadata if needed, plus immutable project/revision folders. Never share a live SQLite file between computers.
- M5: FastAPI/Pydantic, managed PostgreSQL/Auth/Storage; Supabase is the initial managed-service proposal, not an existing account.
- Package backend containers on Linux CI/server. Run the Windows Blender worker natively and let it connect outbound to the API; do not expose Blender ports publicly.
- M4: provider adapter for cloud AI with environment-based credentials, mocked responses in normal tests, structured outputs and bounded tool execution. Coding-assistant login is not an application credential.
- No JEGA API, MCP server, special image provider or 3D interchange compatibility is assumed. Verify any new integration before depending on it.
- Suggested layout: `src/exterior_agent/{domain,geometry,blender,runtime,cli}`, `tests/{unit,integration}`, `examples/`, `scripts/`, `docs/`, `.github/workflows/`. Adapt to an existing repository rather than creating duplicate stacks.
- Keep `bpy` inside the Blender adapter, storage behind an interface, and AI planning separate from tool execution. Add API, cloud queue and UI modules only at the milestone that needs them.

## 6. Data and execution contracts

- `project.json`: `schema_version`, `project_id`, `project_revision`, `input_mode`, normalized units, provenance-aware parameters, materials, camera definitions and render profile.
- Use metres internally; preserve source units and conversion records. Validate positive dimensions, finite numbers, site fit, opening bounds and overlaps before generating geometry.
- Host CLI invokes a fixed Blender script with validated JSON paths and an argument array, never a shell command generated by AI. Use timeouts, captured logs and cancellation.
- Save the model before rendering. Track `queued`, `running`, `completed`, `failed`, `cancelled`, plus per-camera results. Mark complete only after all required artifacts validate.
- Resume missing views only when scene/revision, asset hashes, Blender/tool versions and render configuration match. Never mix attempts or revisions in one delivered set.
- Record timings and failures per stage/view. Preserve useful partial output when a job fails or is cancelled; clean only known temporary files according to a retention policy.

## 7. Canonical cameras and output

Use Z-up; front = −Y, rear = +Y, left = −X, right = +X. Left/right mean the owner's view while standing outside facing the front. Fit cameras to the building/site bounds with padding.

| Camera ID | View |
| --- | --- |
| `01_front` | Front |
| `02_rear` | Rear |
| `03_left` | Left side |
| `04_right` | Right side |
| `05_front_left` | Front-left oblique |
| `06_front_right` | Front-right oblique |
| `07_rear_left` | Rear-left oblique |
| `08_rear_right` | Rear-right oblique |
| `09_top` | Orthographic top-down roof and site |
| `10_aerial` | Elevated oblique showing roof and surroundings |

- Top view includes the roof; a roof-hidden interior plan is a separate future feature. Save all cameras in `.blend`; allow uniquely named additional views later.
- Preview profile: 1280 × 720; final profile: 1920 × 1080 after scene review. Both are 16:9. Higher resolutions are optional, benchmarked settings.
- Use a lightweight Eevee preview where compatible; validate Cycles/OptiX on the actual GPU before using it. Provide a CPU smoke-test path; never assert GPU success from CPU tests.
- Deliver `model.blend`, `model.glb`, named images, labelled contact sheet, `project.json`, `delivery.json`, and licensed textures in `materials/` when used.
- `delivery.json` includes revision, tool versions, render settings, completeness, unresolved assumptions, file paths and checksums. Pack Blender resources or use portable relative paths.
- `.blend` must retain separately named editable walls, roof, openings, doors, windows, site and materials. Verify GLB scale/geometry/materials independently; add FBX only when required and tested.

## 8. M0/M1 acceptance and developer experience

- Provide a working CLI/script to validate the demo, generate the house, render ten views sequentially, export assets and package the result into a fresh revision directory.
- Allow changing width/depth/height and opening parameters without editing implementation code. Re-running with changed parameters must create matching new geometry and images.
- Meaningful tests: invalid/missing values, unit conversion, site fit, actual openings, dimensions within specified tolerance, ten unique correctly oriented cameras and framing.
- Run real headless Blender integration tests: all ten views at a tiny 16:9 resolution such as 128 × 72, save/reopen `.blend`, export/reimport GLB and validate scene contents plus the manifest.
- Test failure/cancellation and rerun behavior. Do not use exact pixel equality across different GPU/driver/Blender versions; use structural and bounded image checks.
- Document one independent GLB viewer check; an exporter returning success alone is insufficient. Record any manual check as manual, not as an automated test.
- README includes Windows PowerShell setup, environment isolation, Blender path configuration, exact commands, output locations, limitations and troubleshooting. Scripts handle spaces in paths.
- Add a `doctor` command/script for Python/Blender versions, configured paths and device availability. Record measured RAM/VRAM/runtime where available; do not invent performance or promise 4K.
- In M0, establish and document real commands for Ruff, pytest and Blender smoke checks; subsequent reports must use those commands. Never list commands as working before their entry points exist.
- If Blender/GPU is unavailable, complete independently verifiable code/configuration and provide exact remaining checks; mark the milestone partially verified, not passed.

## 9. Multi-machine consistency (M5)

- Central database stores project ownership, revisions, jobs, attempts and worker identities. Private object storage stores immutable files by project/revision/job/attempt.
- Edits use optimistic concurrency: a submitted base revision must match; reject conflicts without overwriting another user's work. Do not merge binary `.blend` files automatically.
- Start with PostgreSQL jobs and short atomic claims using row locks / `SKIP LOCKED` as appropriate. Never hold a DB transaction throughout a render.
- Claims include `worker_id`, `attempt_id`, `lease_id`, `lease_expires_at`; use server time, heartbeat renewal and controlled retries. Accept updates/results only for the current valid lease.
- Processing is at-least-once: retries may render twice. Use scoped idempotency keys with payload checks and conditional result publication; stale attempts must not publish as current.
- Upload into attempt-specific paths; validate required files/checksums and lease before atomically publishing accepted metadata. A late old revision must not replace a newer revision.
- Initially assign the whole camera set to one worker. Any later split must share one immutable scene snapshot, assets and compatible versions, followed by a completeness check.

## 10. Security and privacy

- Validate Auth tokens and project/job/file ownership on every API operation. Use revokeable per-worker identities with access only to assigned jobs; keep admin and AI secrets at the trusted backend.
- Use private buckets, scoped expiring download/upload authorization and tested RLS. A service-role key bypassing RLS requires explicit application authorization checks; never put it in a browser or worker.
- Treat uploaded CAD, images, metadata and documents as untrusted data, including instructions embedded in them. AI tools have an allowlist and strict schemas; no arbitrary shell/Python execution tool.
- Enforce actual file type, size, extraction paths, asset references, time and memory limits. Run Blender with low privileges and restricted credentials/network; disable embedded script auto-run on imported `.blend` files. This alone is not a sandbox.
- Keep secrets in environment/secret stores and out of git, prompts, artifacts and logs. Commit only `.env.example` placeholders; redact logs and signed URLs. Use HTTPS and separate staging/production secrets.
- Keep audit logs for access/revision/job/publication/deployment events. Back up both database and storage objects and test restoration; a database backup does not back up image/model bytes.

## 11. Concurrent users and overload (M5)

- The API validates and atomically admits a bounded job, returns its ID and serves status; render work runs in workers. Separate web concurrency from GPU throughput.
- Limit requests, per-user/global queued and running jobs, scene complexity, image size/count, storage and AI/GPU budgets. Reject excess work with suitable 429/503 responses and retry guidance; show meaningful queue status.
- Admission, quota reservation and idempotency must hold across API replicas. Release/reconcile reservations on terminal states; use fair scheduling so one user cannot consume all capacity.
- Preserve capacity for heartbeat, cancellation and result publication under load. Use bounded retries with exponential backoff/jitter; prevent retry storms when AI/providers fail.
- Keep PostgreSQL authoritative. Add Redis for shared rate counters/cache only when needed; increment/expiry must be atomic, caches scoped by access/revision/settings/version. Define durable fallback or pause costly admission on Redis failure.
- Consider Cloudflare for public endpoints; edge limits do not replace exact backend quotas. Upload large files directly to private Storage with scoped authorization where practical.
- Scale stateless API replicas behind a load balancer with a bounded total DB connection pool. Scale GPU workers separately using queue age/runtime, with cost caps and safe drain on shutdown.
- Measure API latency/error rate, oldest queued job, job duration, RAM/VRAM, rejected work and AI spending. Choose global queue/wait limits from measurements; do not claim a supported user count without load evidence.

## 12. CI/CD and release gates

- PR CI: formatting/lint, unit/schema tests, relevant integration tests, all-ten-view low-resolution Blender smoke, dependency audit. Pin compatible versions and third-party Actions to full commit SHAs; use least workflow permissions.
- Build release backend/worker artifacts once with commit/version/checksum metadata. Stage and promote the same artifacts; check API/worker/schema/Blender compatibility before accepting jobs.
- Staging: Auth/upload/job/render/download end-to-end, ownership isolation, competing claims, lease expiry, stale results, idempotency, revision conflicts, cancellation and restore checks.
- Add `k6` load tests with explicit profile/latency/error/business thresholds that block release. Exercise overload/fairness, shared quotas, pool limits, worker outages and Redis/provider failures, including recovery.
- Mock expensive AI/render stages for API load tests; benchmark real scenes/GPU separately with bounded jobs and cost. Do not equate virtual users with render capacity or silently count expected throttling as a regression.
- GPU/OptiX validation uses a trusted staging worker. Never run untrusted PR code with production secrets or on the owner's personal render worker.
- Use compatible migrations, rollback/recovery instructions, health checks and post-release smoke tests. Treat destructive data migrations separately; application rollback cannot undo every migration.
- Configure protected checks/environments when the hosting plan supports them. Prefer short-lived deployment credentials where supported; no automatic production release without the owner's deployment instruction.

## 13. Start and handoff checklist

1. Read actual project instructions and git state; identify existing work. Do not overwrite another project, run destructive git commands or invent a git remote.
2. Verify Superpowers for Claude Code and inspect Python/Blender prerequisites without installing unrelated tools. Summarize the first milestone and open decisions using this brief.
3. Prepare/review the M0/M1 spec and implementation plan through the skills above, then execute the authorized scope with real tests and regular concise Vietnamese progress updates.
4. At each handoff, report changed behavior, artifact paths, exact checks/results, remaining limitations and the next runnable command. Distinguish implemented, mocked, manual, skipped and blocked checks.
5. Maintain `docs/STATUS.md` with completed milestone, pending tasks, verified commands, versions and unresolved issues so another session can continue without repeating work. Never put secrets there.

Reference: [Superpowers](https://github.com/obra/superpowers), [Claude project memory](https://code.claude.com/docs/en/memory), [Claude plugins](https://code.claude.com/docs/en/plugins). Verify changing software/service details against primary documentation at implementation time.

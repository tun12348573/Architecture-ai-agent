# STATUS

Cập nhật: 2026-10-19 · Nhánh: `main` (đã merge `m0-m1`) · Không có git remote.

## Milestone

**M0 + M1: đã triển khai, kiểm chứng cục bộ — xác minh một phần** (CI chưa chạy thật; kiểm tra GLB bằng viewer độc lập chưa làm).

- Spec: [docs/superpowers/specs/2026-10-19-m0-m1-design.md](superpowers/specs/2026-10-19-m0-m1-design.md)
- Plan: [docs/superpowers/plans/2026-10-19-m0-m1.md](superpowers/plans/2026-10-19-m0-m1.md)

## Đã làm

- CLI `exterior-agent validate | build | doctor` (`src/exterior_agent/cli/main.py`).
- Schema `project.json` có provenance (`value/unit/source/source_ref/status`), quy đổi đơn vị về mét, validate gom lỗi theo đường dẫn.
- Hình học thuần Python: tường là mesh kín có **lỗ thật**, mái bằng, đất, bối cảnh; 10 camera chuẩn fit theo hộp bao với padding 10%.
- Script Blender cố định: `build_scene.py` (dựng → lưu `.blend` → xuất `.glb`), `render_views.py` (render tuần tự), `inspect_scene.py` (kiểm tra).
- Runner: thư mục revision bất biến, `job.json`, resume theo fingerprint + checksum, huỷ (Ctrl+C), timeout, giữ kết quả dở, đóng gói `delivery.json` có checksum, contact sheet.
- M0: `pyproject.toml`, `requirements.lock`, `scripts/check.ps1`, `scripts/lock.ps1`, CI `.github/workflows/ci.yml`, README, [chính sách phiên bản](dependency-policy.md).

## Lệnh đã kiểm chứng (2026-10-19, laptop chủ dự án)

| Lệnh | Kết quả |
| --- | --- |
| `.\scripts\check.ps1` (có `EXTERIOR_AGENT_BLENDER`), sau đợt sửa review | ruff check OK, ruff format OK (52 file), unit **111 passed**, integration **10 passed** (Blender 5.2.2 thật), pip-audit: không có lỗ hổng |
| `exterior-agent build "examples\demo_house\project.json" --profile smoke` | completed → `output\demo-townhouse\r001-af814768\` (`delivery.json` có `code_hash`) |
| `exterior-agent doctor` | Python 3.13.3; pydantic 2.14.1; pillow 13.0.0; Blender 5.2.2 LTS, Python nhúng 3.13.13; Cycles thấy OPTIX + CUDA (RTX 3050 Ti); RAM 7.42 GB tổng, **0.87 GB trống** lúc đo; nvidia-smi 4096 MiB, driver 566.07 |
| `exterior-agent validate "examples\demo_house\project.json"` | OK, liệt kê 24 giá trị `needs_review` |
| `exterior-agent build "examples\demo_house\project.json" --profile preview` | completed → `output\demo-townhouse\r001-ee6f32d5\` |
| `exterior-agent build ... --profile preview --engine cycles --device gpu` | completed bằng **CUDA** → `output\demo-townhouse\r001-88e2be54\` (lần đầu lỗi OptiX, lần chạy lại resume bằng CUDA) |

Test integration với Blender thật (128×72, Cycles CPU): dựng scene, mở lại `.blend` đủ đối tượng/collection/vật liệu, kích thước ±1 mm, ray-cast xác nhận lỗ cửa thật, import lại GLB khớp ±1 mm, đủ 10 view, đổi tham số → revision mới đúng hình học, huỷ rồi chạy tiếp, `--out` tương đối.

## Số đo thời gian (thủ công, 2026-10-19)

| Cấu hình | Thời gian |
| --- | --- |
| `smoke` 128×72 Cycles CPU 4 samples, build đầy đủ | ~3 s (dựng + 10 view + đóng gói) |
| `preview` 1280×720 Eevee 16 samples | view đầu 2.6 s, các view sau ~0.3 s; lệnh resume (bỏ qua bước dựng) 8 s tổng |
| `preview` 1280×720 Cycles **CUDA** 16 samples | 0.64–1.12 s/view |

Không đo được RAM/VRAM đỉnh trong lúc render (chưa có công cụ theo dõi). Không có số liệu cho `final` 1920×1080.

## Review toàn nhánh (2026-10-19)

Một reviewer độc lập (subagent, model Opus) review `975d9eb..e087cb7`: kết luận "With fixes", không có lỗi Critical. Đã sửa, mỗi mục có test RED→GREEN:

- Đường dẫn Blender tồn tại nhưng không chạy được → nay thoát mã 3 thay vì traceback.
- Resume có thể trộn ảnh từ code khác nhau → fingerprint và `delivery.json` có `code_hash` (hash mọi file `.py` của package, gồm script Blender).
- Lưới tường bị lệch số thực (vd. `0.7 + 1.4 ≠ 2.1`) tạo mặt suy biến → làm tròn 1 µm và kẹp trong biên.
- Có `original` thì bỏ qua quy đổi đơn vị (3 ft thành 3 m) → đã sửa; `original.unit` được kiểm tra.
- Kiểu dữ liệu lỏng (`true`, `"3.6"`) → nay báo lỗi; số nguyên vẫn hợp lệ.
- Handler output lỗi làm treo tới timeout → vẫn đọc tiếp pipe, stage báo `failed`.
- Hai build chạy cùng lúc → khoá `.exterior-agent.lock` theo thư mục output (mã 2).
- Thêm test timeout cấp runner (hành vi vốn đúng).

Hoãn (minor): CLI gợi ý "chạy lại để resume" kể cả khi resume sẽ bị từ chối; `delivery.json` ghi `complete: true` trước bước verify cuối; key `timings_seconds` (spec ghi `timings`); chưa ghi backend GPU thực dùng; chưa kiểm hướng camera bên trong `.blend` bằng test integration; `scene_plan.json` trên đĩa không kiểm lại khi resume; CI chạy hai lần cho nhánh có PR.

Lưu ý: hai thư mục preview `r001-ee6f32d5`, `r001-88e2be54` được tạo trước đợt sửa nên `delivery.json` của chúng không có `code_hash`.

## Kiểm tra thủ công

| Kiểm tra | Trạng thái |
| --- | --- |
| Contact sheet preview: hướng 10 view (cửa trước bên trái, sân trước ở đáy ảnh top, aerial từ trước-phải) | **Đã xem bằng mắt — đúng** |
| Mở `model.glb` bằng viewer độc lập (README mục "Kiểm tra GLB") | **Chưa làm — chờ chủ dự án** |
| Cycles **OptiX** | **Lỗi**: `COMPILE ERROR: unable to compile with new backend: unimplemented PTX intrinsics` (driver 566.07). Giả thuyết: driver quá cũ cho Blender 5.2 — chưa kiểm chứng |
| Cycles **CUDA** | Render được (log `EA_DEVICE {"gpu": "CUDA: NVIDIA GeForce RTX 3050 Ti Laptop GPU"}`) |

## Chưa kiểm chứng / tồn đọng

- **CI chưa từng chạy**: repo chưa có remote. Workflow đã parse YAML hợp lệ, action ghim SHA; bước cài thư viện hệ thống cho Blender trên Ubuntu và `scripts/install_blender_ci.sh` **chưa chạy thật**.
- Eevee trên Linux CI không được dùng (CI dùng Cycles CPU).
- Profile `final` chưa chạy.
- File lạc `C:\output\demo-townhouse\r001-ee6f32d5\images\.tmp_01_front.png` do lỗi đường dẫn tương đối (đã sửa) tạo ra; công cụ không được phép xoá ở gốc ổ C — **chủ dự án xoá thư mục `C:\output` bằng tay**.
- RAM trống thấp (0.87 GB lúc đo): nên đóng ứng dụng khác khi render `final`.
- 24 giá trị đề xuất trong fixture demo vẫn `needs_review` (dày tường, mái, lỗ cửa, vật liệu).

## Phiên bản

Python host 3.13.3 · Blender 5.2.2 LTS (Python nhúng 3.13.13) · pydantic 2.14.1 · pillow 13.0.0 · pytest 9.1.1 · ruff 0.17.1 · pip-audit 2.10.1 · actions/checkout v7.0.1, setup-python v7.0.0, cache v6.1.0 (ghim SHA).

## Bước tiếp theo

1. Chủ dự án: kiểm GLB bằng viewer độc lập; duyệt các giá trị `needs_review`; xoá `C:\output`.
2. Tạo remote GitHub (khi chủ dự án quyết định) để CI chạy thật; sửa nếu bước cài Blender trên Ubuntu lỗi.
3. Lên spec/plan M2 (template tầng, ban công, mái, vật liệu + benchmark độ phức tạp).

Lệnh chạy tiếp ngay: `.\scripts\check.ps1` rồi `exterior-agent build "examples\demo_house\project.json"`.

# STATUS

Cập nhật: 2026-10-19 · Nhánh: `main` · Remote: https://github.com/tun12348573/Architecture-ai-agent (public).

## Milestone

**M0 + M1: PASSED** — kiểm chứng cục bộ, CI GitHub Actions xanh (run 39234429907), GLB qua Khronos glTF-Validator (kiểm tra thủ công).

- Spec: [docs/superpowers/specs/2026-10-19-m0-m1-design.md](superpowers/specs/2026-10-19-m0-m1-design.md)
- Plan: [docs/superpowers/plans/2026-10-19-m0-m1.md](superpowers/plans/2026-10-19-m0-m1.md)

## M2b — ảnh gần như thật (nhánh `m2b`, 2026-10-20)

**Đã triển khai, kiểm chứng cục bộ; chờ review cuối + merge.** Plan: [2026-10-19-m2b-photoreal.md](superpowers/plans/2026-10-19-m2b-photoreal.md).

- 11 tài sản CC0 Poly Haven (8 texture 1k, HDRI `kloofendal_48d_partly_cloudy_puresky` 2k, cây `shrub_01`/`shrub_02` 1k), 35 file, 30 MiB; `exterior-agent assets fetch` thật: 35 tải về, chạy lại 35 bỏ qua. Poly Haven chặn User-Agent mặc định của urllib → đã đặt User-Agent riêng.
- Vật liệu PBR (màu, độ nhám, normal map theo UV mét), bầu trời HDRI, cây glTF trên bồn mái, `.blend` đường dẫn tương đối (kiểm cả khi chép thư mục sang chỗ khác), GLB có texture.
- Profile `final`: Cycles GPU (CUDA) 1920×1080, **128 samples** (chủ dự án chọn sau benchmark), khử nhiễu OpenImageDenoise; cảnh có HDRI dùng AgX và đèn mặt trời 1.0 (ảnh benchmark trước đó bị cháy sáng nền).
- Benchmark thật 2026-10-20 (`output\benchmarks\modern-townhouse\20261020T015749Z`, 2 view): 64 → 14.1 s/ảnh, 128 → 17.3, 256 → 23.8, 512 → 37.2; VRAM đỉnh ~1247 MiB; RAM trống thấp nhất **0.08 GB** (mẫu lấy lúc bắt đầu render mức samples đầu tiên, không phải lúc dựng scene). Ảnh 64 và 512 gần như không phân biệt.
- Lưu ý: tên thư mục `r###-<hash8>` băm từ project đã chuẩn hoá + cài đặt render; M2b thêm field mới (mặc định rỗng) và đổi profile `final`, nên project 1.0/M2a không đổi tham số vẫn ra tên thư mục mới **một lần** khi build lại (revision cũ giữ nguyên).
- Build final thật: `exterior-agent build "examples\modern_townhouse\project.json" --profile final` → `output\modern-townhouse\r001-5694135f\`, **3.6 phút** cho 10 ảnh (17–20 s/ảnh). Contact sheet xem bằng mắt (manual): texture, HDRI, pergola gỗ, lan can kính hiện rõ; nền đã hết cháy trắng.
- Còn kém (chưa xử lý): nền xung quanh là mặt phẳng xám trơn; xe/xe máy là khối mẫu; cây trên mái nhỏ, thưa.

## M2a — template nhà phố hiện đại (đã merge vào `main`, 2026-10-19)

**Đã triển khai, review cuối xong, merge vào `main`; chưa push lên GitHub.** Spec: [2026-10-19-m2-modern-townhouse-design.md](superpowers/specs/2026-10-19-m2-modern-townhouse-design.md) · Plan: [2026-10-19-m2a-modern-template.md](superpowers/plans/2026-10-19-m2a-modern-template.md).

- `schema_version 1.1`, `template: "modern_townhouse"`; project `1.0` cho `scene_plan` y hệt trước (test hash vàng).
- 1–5 tầng có lỗ cửa thật, tầng lùi + terrace (lan can kính, pergola), ban công kính, khung bao chữ U, lam đứng, ô văng, cửa nhôm kính 4 cánh có dải kính trên, cửa sổ có khung, tường chắn mái, tum thang, vườn sân thượng, sân trước (lát/cỏ), cổng nan, rào, xe/xe máy khối mẫu; UV box-mapping theo mét.
- `.\scripts\check.ps1` (sau review cuối): ruff OK, unit **190 passed**, integration **16 passed** (Blender 5.2.2 thật), pip-audit sạch.
- Review cuối (subagent Opus): "With fixes", 0 Critical. Đã sửa: kiểm tra hình học chung (tên trùng, ra ngoài lô, phần bị lộn/quá nhỏ, chồng lấn giữa mọi thành phần — tường trừ lỗ cửa) chạy sau validate tham số; `terrace_pergola` không có terrace → lỗi; `_stop` luôn dừng Blender khi dừng cả cây thất bại; test giá trị UV trong Blender và build cấu hình tối thiểu.
- Hoãn (minor): giới hạn 25 m chưa tính pergola mái (2.6 m) khi tum thang thấp hơn.
- `exterior-agent build "examples\modern_townhouse\project.json"` (preview Eevee, màu phẳng) → `output\modern-townhouse\r001-aff0478b\`, ~0.3 s/view, 10.6 s tổng. Contact sheet xem bằng mắt: đủ thành phần, hướng 10 view đúng (manual).
- Sửa thêm trong lúc làm: `run_blender` giờ dừng **cả cây tiến trình** khi timeout/huỷ (trước đó tiến trình cháu giữ pipe 10 s và bị bỏ mồ côi).
- Tiếp theo: **M2b** — tài sản CC0 (texture, HDRI, mô hình), vật liệu PBR, profile `final` Cycles CUDA + khử nhiễu, lệnh `benchmark`, `materials/` + `LICENSES.json` trong gói giao.

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

CI GitHub Actions (ubuntu-24.04, Python 3.13.16), run https://github.com/tun12348573/Architecture-ai-agent/actions/runs/39234429907, commit `421411d`, 2026-10-19: lint/format OK, unit **114 passed**, pip-audit sạch, tải Blender 5.2.2 Linux **SHA256 OK**, integration **10 passed** (Cycles CPU 128×72, đủ 10 view), tổng 3 phút 3 giây.

Fixture demo: chủ dự án xác nhận cả 24 giá trị đề xuất (2026-10-19) → `project_revision` 2, `exterior-agent build` preview → `output\demo-townhouse\r002-aec3ecd0\`, `complete: true`, `unresolved_assumptions: []`.

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
| Mở `output\demo-townhouse\r001-ee6f32d5\model.glb` bằng viewer độc lập (gltf-viewer.donmccurdy.com, 2026-10-19, chủ dự án) | **Đã làm — manual**: file mở được; thấy khối nhà mái bằng, sân trước/sau, cửa đi D01 bên trái và cửa sổ W01 là lỗ thật trên mặt tiền, vật liệu có màu. Khronos glTF-Validator 2.0.0-dev.3.10 (generator Khronos glTF Blender I/O v5.2.40): **0 lỗi, 0 cảnh báo**, 4 Info `NODE_EMPTY` tại `/nodes/2–5` = 4 Empty `Opening_*` (cố ý); 11 draw calls, 6 materials, 436 vertices, 304 triangles, không extension. Nhận xét chủ dự án: hình còn sơ sài (đúng phạm vi M1) |
| Cycles **OptiX** | **Lỗi**: `COMPILE ERROR: unable to compile with new backend: unimplemented PTX intrinsics` (driver 566.07). Giả thuyết: driver quá cũ cho Blender 5.2 — chưa kiểm chứng |
| Cycles **CUDA** | Render được (log `EA_DEVICE {"gpu": "CUDA: NVIDIA GeForce RTX 3050 Ti Laptop GPU"}`) |

## Chưa kiểm chứng / tồn đọng

- Eevee và GPU không chạy trên CI (CI dùng Cycles CPU); GPU chỉ được kiểm thủ công trên laptop (CUDA được, OptiX lỗi).
- Profile `final` 1920×1080 chưa chạy.
- RAM trống thấp (0.87 GB lúc đo): nên đóng ứng dụng khác khi render `final`.
- Các mục minor đã hoãn (xem mục Review toàn nhánh).

## Phiên bản

Python host 3.13.3 · Blender 5.2.2 LTS (Python nhúng 3.13.13) · pydantic 2.14.1 · pillow 13.0.0 · pytest 9.1.1 · ruff 0.17.1 · pip-audit 2.10.1 · actions/checkout v7.0.1, setup-python v7.0.0, cache v6.1.0 (ghim SHA).

## Bước tiếp theo

1. Review cuối + merge M2b, push `main` để CI chạy.
2. Sau đó: tân cổ điển (mẫu C) hoặc cải thiện bối cảnh (nền, cây, xe) — chờ chủ dự án chọn.

Lệnh chạy tiếp ngay: `.\scripts\check.ps1` rồi `exterior-agent build "examples\demo_house\project.json"`.

# M2 — Thiết kế: template nhà phố hiện đại, ảnh gần như thật

Ngày: 2026-10-19 · Trạng thái: **chờ chủ dự án duyệt** · Nền: M0+M1 đã PASSED (`docs/STATUS.md`).
Ký hiệu: **[chủ dự án]** = chủ dự án đã chọn trong buổi trao đổi (phác thảo lưu ở `.superpowers/brainstorm/`); **[đề xuất]** = quyết định của người viết spec, chủ dự án có thể sửa.

## 1. Mục đích

Chủ dự án làm chủ yếu nhà dân dụng, gần đây nhất là nhà phố 3 tầng mái bằng hiện đại có sân vườn trên sân thượng, sân trước để đậu ô tô/xe máy hoặc làm vườn [chủ dự án]. Ảnh M1 (hộp chữ nhật màu phẳng) "sơ sài": nhà chỉ là hình chữ nhật thì thiếu thẩm mỹ [chủ dự án]. Ảnh đưa cho khách phải **gần như thật** [chủ dự án].

M2 tạo **template nhà phố hiện đại** dựng từ tham số: khối nhà được phá vỡ (khung, ban công, tầng lùi, lam, ô văng), cửa có khung, sân thượng có vườn, sân trước có cổng, vật liệu PBR có texture, bầu trời HDRI, render Cycles GPU — giữ mọi nguyên tắc M1 (một scene, 10 view, revision bất biến, provenance, checksum).

**Mục tiêu**
- Template `modern_townhouse` với 6 thành phần bật/tắt được [chủ dự án, chọn cả 6]: (1) ban công lan can kính, (2) khung bao dày đua ra, (3) lam chắn nắng đứng, (4) tầng trên lùi + terrace pergola, (5) ô văng/mái hiên tầng 1, (6) cổng + hàng rào ranh trước.
- Tầng 1: **cửa nhôm kính 4 cánh khung sẫm màu + dải kính cố định phía trên** [chủ dự án, mẫu A2-1]; hai cánh giữa là lối đi.
- 1–5 tầng; chiều cao tầng 1 và các tầng trên đặt riêng [đề xuất].
- Sân thượng: tường chắn mái, tum thang lùi về phía sau, vườn + pergola phía trước [chủ dự án].
- Sân trước: `parking` (lát gạch, ô tô + xe máy làm vật mẫu) hoặc `garden` [chủ dự án].
- Vật liệu PBR có texture, HDRI, cây và xe là mô hình — chỉ dùng tài sản **CC0** có ghi nguồn/giấy phép [đề xuất].
- Đo hiệu năng trước khi mở rộng (brief M2): thời gian/ảnh và VRAM thật trên RTX 3050 Ti 4 GB.

**Không làm trong M2**
- Phong cách tân cổ điển (mẫu C: trụ, phào chỉ, cửa vòm, con tiện, mái mansard) — **làm ngay sau M2** [chủ dự án]. M2 phải chừa chỗ cắm phong cách (mục 4).
- Công trình công giáo, mái dốc, nội thất, cầu thang trong nhà, cửa sổ tường bên (nhà ống sát ranh), DXF/ảnh (M3), AI (M4).

**Phản mục tiêu**
- Texture/HDRI/mô hình không rõ giấy phép, hoặc không ghi nguồn trong gói giao.
- Project M1 (`schema_version 1.0`) không còn build được hoặc ra hình khác.
- Render tràn VRAM rồi treo/crash im lặng thay vì báo lỗi rõ.
- Chi tiết "đẹp" nhưng sai kích thước (ban công vượt ranh đất, cửa xuyên khung…).
- Texture có trong `.blend` nhưng mất trong `.glb` mà không ghi rõ.
- Báo thời gian render mà không đo.

## 2. Dùng lại từ M1

Giữ nguyên: CLI `validate|build|doctor`, provenance `Param`, chuẩn hoá đơn vị, `scene_plan.json`, runner (revision bất biến, resume theo fingerprint + `code_hash`, khoá một build, huỷ/timeout), 10 camera chuẩn, gói giao có checksum, Blender 5.2.2. Mesh tường có lỗ thật được tổng quát hoá cho nhiều tầng.

## 3. Mô hình dữ liệu (`schema_version: "1.1"`)

`1.0` vẫn hợp lệ và cho kết quả như M1 [đề xuất]. `1.1` thêm `template: "modern_townhouse"` và khối `modern` (mọi số là `Param` có provenance):

- `floors[]` (1–5): `height`, `openings_front[]`, `openings_rear[]`. Tầng 1 mặc định có cửa `door_4leaf` (rộng, cao, cao dải kính fix).
- `setbacks[]`: tầng `i` lùi khỏi mặt tiền `d` m → sàn tầng dưới lộ ra thành terrace (lan can kính + tuỳ chọn pergola).
- `balconies[]`: tầng, rộng, đua ra, cao lan can (mặc định 1.1 m), dày sàn.
- `frames[]`: bao các tầng `[from, to]`, dày, đua ra.
- `louvers[]`: tầng, vùng phủ (offset, width), số lam/khoảng cách, tiết diện lam.
- `canopy`: cao độ, đua ra, dày (che cửa tầng 1).
- `roof`: cao tường chắn mái, `stair_head` (rộng, sâu, cao, sát tường sau), `garden` (bồn cây dọc mép trước, pergola có/không).
- `front_yard`: `kind ∈ parking|garden`, `gate` (rộng, cao), `fence_height`, vật mẫu (`car`, `motorbikes: n`).
- `materials`: chọn theo **id tài sản** trong danh mục (mục 6) cho các vai trò: tường sơn, khung/ốp, nhôm khung cửa, kính, lam, sàn terrace, gạch sân, cỏ, đất bồn, gỗ pergola.

**Validate thêm**: mọi thứ nằm trong lô đất (ban công/ô văng được đua ra trên sân trước nhưng không vượt ranh trước); tầng lùi < sâu nhà; tổng chiều cao ≤ giới hạn cấu hình [đề xuất: 25 m]; ban công/khung/lam không cắt qua lỗ cửa; tum thang nằm trong mái; 1–5 tầng; id vật liệu có trong danh mục.

## 4. Kiến trúc: lõi chung + phong cách cắm được

- **Lõi** (thuần Python, test không cần `bpy`): lô đất, khối tầng xếp chồng + lùi, tường có lỗ thật nhiều tầng, sàn/mái, tum thang, tường chắn mái, sân, cổng/rào; primitive dùng chung: hộp, tấm có lỗ, khung chữ nhật (profile), dãy lam, lan can kính.
- **UV**: lõi sinh UV kiểu box-mapping theo kích thước thật (m) cho mọi mesh [đề xuất] → texture đúng tỉ lệ ở cả `.blend` lẫn `.glb`.
- **Phong cách** `modern`: quyết định thành phần nào xuất hiện và dạng chi tiết (cửa nhôm 4 cánh, lan can kính, khung dày). Tân cổ điển sau này là module phong cách khác dùng cùng lõi + primitive mới (vòm, trụ, phào, con tiện).
- `scene_plan.json` mở rộng: object có `material` theo vai trò; thêm `assets[]` (mô hình cây/xe: id, vị trí, xoay, tỉ lệ) và `world` (HDRI id, cường độ, xoay). Tên object: `Floor{n}_*`, `Balcony_F{n}`, `Frame_F{a}-{b}`, `Louver_F{n}_{k}`, `Canopy`, `Parapet`, `StairHead`, `Pergola_*`, `Planter_*`, `Gate`, `Fence_*`, `Door_*`, `Window_*` — mỗi thứ là object riêng, sửa được trong `.blend`.

## 5. Ảnh và hiệu năng

- Profile `final`: Cycles **GPU (CUDA)**, khử nhiễu OpenImageDenoise, 1920×1080, số samples **do benchmark chọn**; mục tiêu ban đầu **≤ 3 phút/ảnh, ≤ 30 phút/bộ 10 ảnh** [đề xuất; chủ dự án hỏi "bao lâu thì tốt nhất" — chốt theo số đo].
- Profile `preview`: Eevee có texture + HDRI, 1280×720, duyệt bố cục nhanh.
- Profile `smoke` giữ cho test/CI, dùng **vật liệu màu phẳng dự phòng** [đề xuất] → CI không cần tải tài sản.
- Lệnh `exterior-agent benchmark <project> --profile final --samples 64,128,256,512`: render 1–2 view đại diện ở mỗi mức, ghi thời gian/ảnh, **VRAM đỉnh** (lấy mẫu `nvidia-smi`), RAM, lưu ảnh để chủ dự án chọn bằng mắt. Kết quả ghi vào STATUS.
- Tràn VRAM / lỗi GPU → stage `failed`, thông báo rõ và gợi ý (giảm cây, giảm samples, `--device cpu`), không treo.

## 6. Tài sản CC0

- Danh mục `assets/catalog.json` (commit): mỗi tài sản có `id`, `kind` (texture|hdri|model), `url` tải từ nguồn chính thức (Poly Haven / ambientCG), `sha256`, `license: "CC0"`, `author`, `source_page`, độ phân giải [đề xuất: texture 1K–2K, HDRI 2K để vừa 4 GB VRAM].
- `exterior-agent assets fetch`: tải vào **cache ngoài git** (`EXTERIOR_AGENT_ASSETS`, mặc định `C:\Tools\exterior-agent-assets`), kiểm SHA256, không chạy gì trong file tải về.
- Gói giao: texture/HDRI đã dùng chép vào `materials/` kèm `LICENSES.json` (id, tác giả, nguồn, CC0) và checksum trong `delivery.json`; `.blend` dùng đường dẫn tương đối tới `materials/` (hoặc pack) để mở được trên máy khác.
- Không có mô hình CC0 phù hợp (ví dụ ô tô) → dùng vật mẫu dựng bằng primitive, ghi rõ trong `delivery.json` [đề xuất].
- Thiếu tài sản khi build `final`/`preview` → lỗi rõ "chạy `exterior-agent assets fetch`", không âm thầm dùng màu phẳng.

## 7. Fixture demo mới

`examples/modern_townhouse/project.json`, ghi "DEMO FIXTURE", mọi số `needs_review` [đề xuất]: lô 5 × 20 m; lùi trước 4.5 m, lùi sau 1 m; footprint 5 × 14.5 m; 3 tầng (tầng 1 cao 3.6 m, tầng 2–3 cao 3.3 m); tầng 3 lùi 2.0 m tạo terrace có pergola; ban công kính tầng 2 đua 1.0 m; khung bao tầng 2 dày 0.3 m đua 0.4 m; lam đứng phủ 1/3 mặt tiền tầng 2; ô văng tầng 1 đua 1.2 m; cửa 4 cánh rộng 3.2 m cao 2.6 m + dải kính 0.5 m; mái: tường chắn 1.1 m, tum thang 3 × 4 × 2.8 m sát tường sau, bồn cây + pergola phía trước; sân trước `parking` có 1 ô tô + 2 xe máy, cổng rộng 3.5 m, rào cao 1.6 m. Fixture M1 `examples/demo_house` giữ nguyên.

## 8. Kiểm thử

- **Unit**: validate từng thành phần (ranh đất, chồng lấn, giới hạn); hình học nhiều tầng kín và lỗ thật; vị trí/kích thước từng thành phần ±1 mm; tầng lùi tạo terrace đúng; UV đúng tỉ lệ mét; danh mục tài sản đúng schema, mọi mục có CC0 + sha256; project 1.0 cho `scene_plan` y hệt M1 (so hash).
- **Integration (Blender thật, `smoke`, màu phẳng)**: build fixture modern → đủ object đặt tên đúng, 10 view, kích thước ±1 mm, lỗ cửa thật (ray-cast), GLB import lại khớp; đổi tham số (bỏ ban công, thêm tầng) → revision mới đúng.
- **Integration có tài sản (chỉ chạy cục bộ khi có cache)**: build `preview` textured → `materials/` + `LICENSES.json` đủ, checksum khớp, `.blend` mở lại không thiếu texture, GLB có texture.
- **Manual + benchmark**: render `final` trên laptop, ghi thời gian/VRAM; chủ dự án duyệt ảnh bằng mắt; ghi rõ manual.
- CI giữ như M0 (không GPU, không tải tài sản).

## 9. Để lại cho người thực hiện

Chọn tài sản CC0 cụ thể (đúng vai trò, độ phân giải trong giới hạn), góc/cường độ HDRI, profile khung nhôm, mật độ cây, chi tiết pergola/cổng, tổ chức module trong `geometry/`, thông báo lỗi.

## 10. Giới hạn đã biết

Chỉ phong cách hiện đại, mái bằng, mặt tiền và mặt sau; tường bên đặc. Ảnh "gần như thật" phụ thuộc tài sản CC0 và 4 GB VRAM; mức samples chỉ chốt sau benchmark. OptiX chưa chạy trên driver hiện tại — dùng CUDA.

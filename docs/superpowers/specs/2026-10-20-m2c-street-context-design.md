# M2c — Thiết kế: bối cảnh phố, vật liệu và cửa chính thật hơn

Ngày: 2026-10-20 · Trạng thái: **chờ chủ dự án duyệt** · Nền: M2b đã merge vào `main` (`docs/STATUS.md`).
Ký hiệu: **[chủ dự án]** = chủ dự án đã nói/chọn; **[đề xuất]** = quyết định của người viết spec, chủ dự án có thể sửa.

## 1. Mục đích

Ảnh `final` M2b (`output\modern-townhouse\r001-5694135f`) vẫn "giả". Chủ dự án chỉ ra ba chỗ: **chất liệu gạch**, **cửa chính** và **xe** [chủ dự án]. Ngoài ra, nền xung quanh nhà là một mặt phẳng xám trơn, và cây trên mái nhỏ, thưa.

Bối cảnh thật của chủ dự án [chủ dự án]:
- **Hai bên** là các nhà dân dụng khác.
- **Phía trước** là đường chính có xe chạy, hoặc một công viên.

M2c làm cho ảnh đưa khách trông như chụp ở một con phố Việt Nam. Các nguyên tắc cũ giữ nguyên:
- Một scene duy nhất cho mọi view.
- Đủ 10 view chuẩn.
- Revision bất biến, có provenance, có checksum.
- Chỉ dùng tài sản CC0.

**Mục tiêu**

1. **Bỏ xe** [chủ dự án]. Trong fixture demo, `car: false` và `motorbikes: 0`. Tham số vẫn giữ để ai cần thì bật lại; khi bật, vật mẫu khối hộp vẫn được ghi trong `placeholders` như trước.
2. **Tường sơn mịn màu sáng** (trắng ngà), thay cho kiểu bê tông xám lốm đốm [đề xuất, chủ dự án đồng ý].
3. **Mảng ốp gạch thẻ** ở mặt tường tầng trệt phía trước [chủ dự án giao cho người viết spec chọn → **[đề xuất]**]:
   - Gồm hai trụ hai bên cửa chính và dải tường trên cửa, lên tới mép sàn tầng 2.
   - Vị trí ốp là tùy chọn; có thể tắt.
4. **Cửa chính 4 cánh (và cửa sổ) thật hơn** [đề xuất, chủ dự án đồng ý]:
   - Khung nhôm xám đậm/đen, dày hơn.
   - Kính trong và phản chiếu trời, qua kính thấy bên trong tối.
   - Hết mảng xanh đục.
5. **Bối cảnh phố**, chọn bằng `context.front`: `road` hoặc `park` [chủ dự án]:
   - **Cả hai kiểu đều có:** vỉa hè lát gạch, bó vỉa, đèn đường.
   - **`road`:** mặt đường nhựa có vạch kẻ.
   - **`park`:** một làn đường nhỏ, rồi bãi cỏ có cây to.
6. **Nhà hàng xóm sát vách** hai bên [chủ dự án: "hai bên là nhà dân dụng khác"; dạng khối là đề xuất]:
   - Nhà phố đơn giản, cao 2–5 tầng, màu sơn khác nhau, có ô cửa và ban công đơn giản.
   - Chỉ làm nền, ít chi tiết hơn nhà chính.
7. **Nền có texture:** gạch lát (sân, vỉa hè), nhựa đường, cỏ. Không còn mặt xám trơn trong khung hình.
8. **Cây nhiều hơn, to hơn:**
   - Một cây to ở sân trước khi sân là `garden`; cây to trên vỉa hè hoặc trong công viên.
   - Chậu cây trên ban công và terrace.
   - Bồn cây trên mái dày hơn.

**Không làm trong M2c**
- Nội thất thật sau kính. Chỉ cần bên trong đọc là tối và có chiều sâu.
- Cảnh ban đêm, đèn đường phát sáng, người, xe trên đường, dây điện.
- Mô hình ô tô thật: Poly Haven không có ô tô CC0.
- Phong cách tân cổ điển (mẫu C): làm sau M2c.
- Điều khiển chi tiết từng nhà hàng xóm.

**Phản mục tiêu**
- Bối cảnh lấn vào lô đất hoặc đè lên nhà chính.
- Bối cảnh làm đổi khung hình các camera chuẩn: camera vẫn fit theo nhà và lô đất.
- Nhà hàng xóm hoặc cây bị coi là số đo thật. Chúng là minh hoạ và phải ghi rõ như vậy trong `delivery.json`.
- Build lại cùng tham số mà ra bối cảnh khác. Bối cảnh phải tất định.
- Laptop hết RAM hoặc VRAM khi build/render, hoặc thời gian render tăng mà không đo.
- Project cũ (1.0, hoặc 1.1 không có khối `context`) cho ra scene khác.
- Tài sản không rõ giấy phép.

## 2. Dùng lại từ M2a/M2b

- Toàn bộ pipeline: validate → `scene_plan.json` → `build_scene.py` → render tuần tự → đóng gói.
- Catalog tài sản ghim sha256, `assets fetch`, staging vào `materials/` cùng `LICENSES.json` (tạo lại khi đóng gói).
- Khoá dùng chung cho cả máy; lệnh `benchmark`.
- Profile `final`: Cycles GPU, 128 samples, OIDN, AgX.
- Cách đặt cây trên mái (`add_plant`). Từ M2b, cây đã xoay đúng `rotation_z` và tâm mesh nằm ở gốc.
- Profile `smoke` vẫn màu phẳng, không cần tài sản. Hình học bối cảnh (đường, vỉa hè, nhà hàng xóm) là Python thuần nên **vẫn có** trong smoke; mô hình glTF (cây, đèn) thì **không**.

## 3. Mô hình dữ liệu (`schema_version` giữ `"1.1"`)

Các thay đổi đều là trường **tùy chọn**. Project không khai báo chúng thì `scene_plan` giữ nguyên (so hash).

- **`context`** (khối cấp project, chỉ dùng cho `modern_townhouse`) [đề xuất]:

  | Trường | Kiểu | Ý nghĩa |
  | --- | --- | --- |
  | `front` | Choice `road` / `park` | Kiểu phía trước |
  | `sidewalk_width` | Length | Rộng vỉa hè, tính từ ranh trước lô ra phía −Y |
  | `road_width` | Length | Rộng lòng đường; với `park` là làn nhỏ trước công viên |
  | `neighbours` | `{ per_side: Count, seed: Count }` hoặc null | Nhà hàng xóm sát vách |
  | `street_lamps` | Flag | Đèn đường |
  | `street_trees` | Flag | Cây to trên vỉa hè/công viên |
  | `pots` | Flag | Chậu cây trên sàn ban công và terrace |
  | `models` | `{ tree, lamp, pot }` là Choice (asset id) | Mô hình dùng cho từng loại |

  Mọi giá trị có provenance (`Param`) như các trường khác.
- **`modern.cladding`** [đề xuất]:
  - Gồm `zone` (Choice, bản đầu chỉ có `ground_front`) và `thickness` (Length, ví dụ 0.02 m).
  - Vật liệu nằm ở `materials.cladding` (texture gạch thẻ).
  - Lớp ốp phải có lỗ đúng bằng lỗ tường, không che cửa.
- **Vật liệu:**
  - Thêm trường tùy chọn `transmission` (0..1, mặc định 0) vào `MaterialSpec`. Kính có `transmission > 0` render trong suốt thật bằng Cycles.
  - Thêm các vai trò tùy chọn: `cladding`, `asphalt`, `sidewalk`, `kerb`, `road_marking`, `neighbour_wall`, `neighbour_glass`. Màu từng nhà hàng xóm được nhân từ `neighbour_wall` với một bảng sắc độ cố định trong code, chọn theo `seed` (vật liệu `MAT_Neighbour_1..n`) [người viết spec chốt].
- **Chậu cây ban công/terrace:** một cờ chung `context.pots` [người viết spec chốt]. Chưa cần bật/tắt riêng từng ban công.

Validate:
- Kích thước dương và hữu hạn; `per_side` từ 0 đến 4.
- Asset id phải có trong catalog và đúng `kind`.
- Cây và chậu không được chạm vào ranh nhà chính hay cửa.
- `cladding` chỉ hợp lệ khi tầng 1 có tường mặt trước.

## 4. Hình học bối cảnh

Hệ trục giữ nguyên: Z hướng lên; mặt trước nằm phía −Y; ranh trước lô ở y = 0; lô chạy x ∈ [−W/2, W/2].

- **Vỉa hè:**
  - Nằm ở y ∈ [−sidewalk_width, 0], cao hơn mặt đường một bó vỉa (≈ 0.15 m) [đề xuất].
  - Bó vỉa là một dải riêng.
- **`road`:**
  - Lòng đường nằm ở y ∈ [−sidewalk_width − road_width, −sidewalk_width].
  - Vạch kẻ giữa đứt đoạn là các quad mỏng nổi rất ít trên mặt đường.
  - Bên kia đường có vỉa hè đối diện, để ảnh không kết thúc bằng mép trống.
- **`park`:**
  - Có làn đường nhỏ rộng `road_width`, sau đó là bãi cỏ.
  - Cây to rải tất định trên bãi cỏ.
- **Nền xa** (`Site_Context`):
  - Vẫn là nền phủ phần còn lại, nhưng dùng texture (cỏ/đất hoặc gạch lát, người thực hiện chọn).
  - Ở các góc chụp chuẩn, không được thấy mép nền hay mặt xám trơn.
- **Nhà hàng xóm:**
  - Mỗi bên `per_side` căn, xếp sát nhau và sát ranh lô (x = ±W/2 trở ra). Bề rộng 4–6 m, chiều sâu gần bằng nhà chính, khoảng lùi trước 0–3 m.
  - Số tầng 2–5, cao 3.3 m mỗi tầng; màu lấy từ `neighbour_wall` nhân với sắc độ theo seed.
  - Tất cả sinh từ `seed` bằng bộ sinh số giả ngẫu nhiên riêng (không dùng trạng thái toàn cục). Cùng tham số cho ra cùng hình.
  - Mặt tiền có ô cửa kính lõm vào và một ban công đơn giản mỗi tầng. Không làm lỗ thật bên trong.
  - Nằm trong collection `Context`, tên object dạng `Neighbour_L1`, `Neighbour_R2`, …
- **Đèn đường:** mô hình glTF, đặt tất định trên vỉa hè, cách đều nhau, không đứng chắn trước cổng.
- Mọi object bối cảnh nằm trong collection `Context`. Hàm tính bounds cho camera **không** tính collection này.
- `delivery.json` thêm khoá `illustrative`: danh sách object và tài sản minh hoạ (collection `Context`, cây, chậu), kèm câu "không phải hiện trạng/số đo" [người viết spec chốt]. Khoá `placeholders` giữ nguyên.

## 5. Vật liệu, ốp gạch và cửa

- **Tường:**
  - Texture sơn/vữa mịn có độ tương phản thấp, `base_color` trắng ngà.
  - Người thực hiện chọn texture CC0 (ứng viên: `beige_wall_001/002`, hoặc giữ `painted_plaster_wall` nhưng đổi màu và độ nhám).
  - Tiêu chí: ở góc `01_front` không còn đọc như bê tông.
- **Ốp gạch thẻ:**
  - Texture gạch CC0 sạch, kiểu hiện đại (ứng viên: `brick_wall_001` …).
  - `scale_m` đúng kích thước viên thật: viên gạch thẻ khoảng 0.06 × 0.24 m, sai lệch ±20%.
  - Hình học là lớp vỏ dày `thickness` áp lên mặt ngoài tường trước tầng 1, từ z = 0 tới đáy ô văng/sàn tầng 2, có lỗ trùng với các lỗ cửa.
- **Khung cửa:**
  - Màu `aluminium` xám đậm (khoảng 0.05–0.08 tuyến tính).
  - Profile cửa 4 cánh rộng 0.08 m, cửa sổ giữ 0.06 m [đề xuất].
  - Đổi profile sẽ làm đổi hash scene plan của fixture modern. Test golden được cập nhật có chủ đích; hash M1 không đổi.
- **Kính:**
  - `window_glass` có `transmission: 1`, độ nhám ≈ 0, IOR 1.45, màu trung tính hơi xanh lục rất nhẹ.
  - Bỏ alpha xanh đục trong ảnh Cycles. Preview Eevee chỉ cần gần đúng.
  - Bên trong nhà là khoang rỗng, chỉ nhận sáng qua cửa nên tự nhiên sẽ tối.
  - Nếu ảnh vẫn thấy bên trong sáng hoặc trống, đặt một tấm nền tối, nhám, cách kính 1.5 m bên trong mỗi lỗ cửa mặt trước (collection `Interior_Backdrop`). Người thực hiện quyết định sau khi xem ảnh, ghi lại trong plan/STATUS.
- **GLB:**
  - Kính xuất bằng `KHR_materials_transmission` (exporter của Blender tự làm). Test kiểm tra trường này có mặt.
  - Gạch và nền phải có texture trong GLB.

## 6. Cây và chậu

- **Cây to:**
  - Một mô hình duy nhất cho mọi cây to [đề xuất]: `island_tree_02` (1k, ~44 MiB). `jacaranda_tree` (205 MiB) và `tree_small_02` (96 MiB) bị loại vì RAM 8 GB.
  - Import **một lần**; các bản sao dùng chung mesh (linked duplicate), xoay và tỉ lệ tất định (góc vàng + tỉ lệ 0.85–1.15).
- **Chậu:** `potted_plant_02` (~2.5 MiB) đặt trên sàn ban công và terrace, sát lan can, không chắn cửa.
- **Bồn mái:** khoảng cách cây giảm từ 1.5 m xuống ~0.8 m. Thêm `shrub_03`/`shrub_04` để đa dạng. Cây không được thò ra ngoài bồn (test bbox như M2b).
- **Đèn đường:** `street_lamp_01` hoặc `_02` (~2 MiB).
- **Ngân sách tài sản mới:** tổng dung lượng glTF thêm vào ≤ ~60 MiB, thêm texture 1k, HDRI giữ nguyên. Vượt ngân sách → giảm số cây, không đổi lên mô hình nặng hơn.

## 7. Hiệu năng (đo, không đoán)

- Chạy lại `exterior-agent benchmark` (128 samples, 2 view) và một build `final` đủ 10 ảnh. Ghi thời gian/ảnh, VRAM đỉnh, RAM trống thấp nhất vào STATUS.
- Mục tiêu [đề xuất]:
  - VRAM đỉnh ≤ 3.5 GB (card 4 GB).
  - Không crash hoặc OOM.
  - Thời gian/ảnh không quá 2× M2b (17–20 s → ≤ 40 s).
- Không đạt: giảm số cây hoặc nhà hàng xóm trong fixture, đo lại. Không tăng tài nguyên.

## 8. Fixture demo

Sửa `examples/modern_townhouse/project.json`, vẫn ghi "DEMO FIXTURE", mọi giá trị mới đều `needs_review`:
- `car: false`, `motorbikes: 0`.
- Khối `context`: `front: road`, vỉa hè 3 m, đường 7 m, mỗi bên 2 nhà hàng xóm, có đèn đường và cây vỉa hè.
- `cladding: ground_front`.
- Kính trong; khung xám đậm; tường trắng ngà.
- Chậu trên ban công tầng 2 và terrace tầng 3; bồn mái dày.

Thêm một biến thể để test `park`: tạo trong test bằng cách chỉnh project. Không thêm fixture thứ ba [đề xuất].

## 9. Kiểm thử

- **Unit (Python thuần):**
  - Schema `context`/`cladding`/`transmission`: giá trị sai bị từ chối.
  - Project không có `context` cho scene plan y hệt trước (hash M1 và hash modern-không-context).
  - Bối cảnh không chồng lên lô đất; nhà hàng xóm sát ranh, không chạm nhà chính.
  - Tất định: hai lần gọi cùng seed cho cùng plan; đổi seed thì đổi chiều cao.
  - Camera không đổi khi bật/tắt bối cảnh.
  - Ốp gạch có lỗ trùng lỗ cửa (±1 mm) và đúng vùng tầng 1.
  - Chậu và cây nằm trong sàn ban công/bồn/vỉa hè.
  - `road` và `park` đều sinh đúng các phần của mình.
- **Integration smoke (Blender thật):** collection `Context` có nhà hàng xóm/đường/vỉa hè; 10 view; `.blend` mở lại được; GLB import lại khớp.
- **Integration có tài sản (chạy cục bộ khi có cache):**
  - Cây to là linked duplicate (cùng `mesh.data`).
  - Chậu và cây đặt đúng chỗ.
  - Kính có transmission trong `.blend` và trong GLB.
  - Texture gạch có trong `materials/` và `LICENSES.json`.
- **Manual:**
  - Build `final`; chủ dự án xem contact sheet, so với ảnh M2b.
  - Benchmark ghi vào STATUS. Ghi rõ đây là bước manual.

## 10. Quyết định đã chốt

1. **Nhà hàng xóm che mặt bên** [chủ dự án, 2026-10-20: "đồng ý"]: bật hàng xóm mặc định. Ở view `03_left`/`04_right` (và một phần các góc chéo phía sau), camera sẽ thấy tường nhà hàng xóm, đúng thực tế. Khi cần xem mặt bên nhà chính, build một revision với `neighbours: null`. README hướng dẫn cách làm này.

## 11. Để lại cho người thực hiện

- Chọn texture CC0 cụ thể theo tiêu chí ở mục 5–6.
- Mẫu vạch kẻ đường; số đèn và cây trên vỉa hè.
- Màu nhà hàng xóm; chi tiết ô cửa của nhà hàng xóm.
- Có cần tấm nền tối sau kính hay không.
- Tổ chức module (gợi ý: `geometry/context.py`, `geometry/modern_cladding.py`).
- Nội dung thông báo lỗi.

## 12. Giới hạn đã biết

- Bối cảnh là minh hoạ, không phải hiện trạng thật.
- Một loại cây to.
- Ban ngày; đèn đường không sáng.
- Không có xe thật.
- Bên trong nhà sau kính chỉ là khoảng tối.
- Mặt bên nhà chính bị hàng xóm che khi bật bối cảnh.

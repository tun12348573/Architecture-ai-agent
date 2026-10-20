# M2d — Thiết kế: nhà phố tân cổ điển (mẫu C)

Ngày: 2026-10-20 · Trạng thái: **đã duyệt** (chủ dự án, 2026-10-20: "duyệt") · Nền: M2c đã merge vào `main` và push, CI xanh (run 39393990963).
Ký hiệu: **[chủ dự án]** = chủ dự án đã nói/chọn; **[đề xuất]** = quyết định của người viết spec, chủ dự án có thể sửa.

## 1. Mục đích

Chủ dự án hay xây nhà phố theo phong cách cổ điển [chủ dự án]. M2 đã chọn "mẫu C" (tân cổ điển) làm sau mẫu hiện đại [chủ dự án]. Ảnh tham chiếu chủ dự án gửi ngày 2026-10-20 cho thấy một nhà phố 3 tầng cộng áp mái:
- Màu trắng, có mảng ốp kem; cửa sổ khung sẫm; cửa chính gỗ.
- Khối nhô bên trái có cột tròn, ban công cong lan can sắt phình, cửa vòm và một hồi tam giác nhỏ có hoa văn đắp.
- Bên phải có ban công con tiện và cửa sổ vòm với ban công tròn.
- Trên cùng là hồi tam giác lớn có cửa sổ tròn.
- Phào dày giữa các tầng, trụ ốp ở góc nhà, cổng sắt uốn với trụ cổng có đèn.

"Nếu thiếu hoa văn thì sẽ khó giống cổ điển" [chủ dự án]. Chủ dự án không có thư viện hoa văn riêng [chủ dự án], và kho CC0 đang dùng (Poly Haven) không có chi tiết kiến trúc cổ điển. Vì vậy mọi hoa văn được **dựng bằng code**.

Bản thử dùng xong bỏ (`output\spike-classic\`, script trong scratchpad) đã dựng bằng code: phào có răng cưa, hồi tam giác, khung vòm có đá khoá, cửa vòm có song chia, cửa gỗ pano, cột có đầu cột lá, ban công sắt phình, con tiện, hoa thị, cửa sổ tròn có hoa văn cuộn. Chủ dự án xem và đồng ý làm tiếp ("rồi") [chủ dự án]. **Mức chi tiết của bản thử là mức chuẩn tối thiểu**: đọc đúng là tân cổ điển khi nhìn cả mặt tiền; nhìn cận thì còn thô.

**Mục tiêu**
1. Template mới `neoclassical_townhouse` dùng chung lõi với `modern_townhouse`: lô đất, tầng, tường có lỗ thật, sân/cổng, bối cảnh phố M2c, 10 camera, gói giao [chủ dự án đồng ý "dùng chung lõi"; tách thành template riêng là **[đề xuất]**].
2. **Mặt tiền bất đối xứng** [chủ dự án]: một **khối nhô** đặt bên trái hoặc phải, phần còn lại lùi vào.
3. **Lỗ cửa vòm thật** (cửa đi và cửa sổ) bên cạnh lỗ chữ nhật; cửa sổ tròn trên hồi.
4. **Ban công:** cong lan can sắt phình, chữ nhật lan can con tiện, hoặc tròn nhỏ đặt trên chân đỡ cong.
5. **Cột tròn** có bệ, thân có độ phình, đầu cột lá (dạng Corinth đơn giản hoá); **trụ ốp** góc nhà có đầu trụ.
6. **Phào** nhiều lớp giữa các tầng và dưới mái, có hàng răng cưa; **khung vòm** có đá khoá; mũ cửa sổ (phào ngắn trên cửa).
7. **Hoa văn đắp:**
   - Hoa văn cuộn và chùm lá quanh cửa sổ tròn.
   - Hoa văn đắp trên hồi nhỏ.
   - Hoa thị.
   - Mức chi tiết tối thiểu như bản thử.
8. **Mái dốc hai mái lợp ngói đỏ, phủ từ trước ra sau** [chủ dự án]:
   - Đỉnh mái chạy dọc chiều sâu nhà; hồi tam giác ở mặt tiền và mặt sau.
   - Độ dốc chỉnh được, mặc định 40° [đề xuất].
   - Máng xối (sê nô) dọc hai tường bên.
9. **Tầng trệt:** cửa gỗ pano 2 cánh có ô kính rẻ quạt phía trên khi cửa là vòm; trụ cổng có đèn (chỉ là mô hình, không phát sáng); cổng và rào sắt.
10. **Màu:** trắng cho chi tiết, kem cho mảng tường (hồi, ô ốp), sắt đen, khung sẫm, cửa gỗ. Mọi màu chỉnh được trong `project.json`.

**Không làm trong M2d**
- Hoa văn chạm tinh xảo (lá acanthus điêu khắc thật, phù điêu người hoặc thú).
- Mái mansard, vòm cầu, tháp.
- Nội thất, kể cả trong áp mái.
- Đèn phát sáng ban đêm.
- Đọc ảnh tham chiếu để tự dựng nhà: đó là M3 trở đi.
- Biến thể mặt sau phức tạp: mặt sau chỉ có cửa đơn giản và hồi trơn.

**Phản mục tiêu**
- Hoa văn hoặc cột thò ra ngoài lô, cắt qua lỗ cửa, hoặc nổi lơ lửng không chạm tường.
- Lỗ vòm là mảng sơn đen chứ không phải lỗ thật (phải ray-cast xuyên qua được).
- Mái để hở khe với tường, hoặc nước mái đổ sang lô hàng xóm (mép mái phải nằm trong ranh lô).
- Bối cảnh M2c (hàng xóm, cây) đè lên mái hoặc ban công.
- Số object bùng nổ: mỗi thành phần đặt tên là **một** object sửa được, không phải hàng nghìn mảnh rời.
- Thời gian render vượt ngưỡng mà không đo; máy 8 GB RAM bị tràn.
- Làm hỏng mẫu hiện đại hoặc M1: hash golden M1 không đổi; fixture modern không đổi hình học.

## 2. Dùng lại

- Từ M1/M2a/M2b/M2c: validate, provenance `Param`, `scene_plan.json`, runner (revision bất biến, resume, khoá chung cả máy), 10 camera fit theo nhà + lô, gói giao có checksum.
- Tài sản CC0: catalog có sha256, `assets fetch`, `LICENSES.json`, `illustrative`, profile `final` (Cycles GPU 128 samples, OIDN, AgX), `benchmark`.
- Từ M2c: khối `context` (đường/công viên, vỉa hè, hàng xóm, cây, đèn, chậu), nền khép kín, `fit` của mô hình, kính `transmission`, tấm nền tối sau kính.
- Lõi `modern_townhouse`: tầng xếp chồng, `floor_frames`, sàn, sân trước, cổng/rào, `context_objects`. Những gì dùng chung được tách ra module lõi khi cần; không sao chép mã.

## 3. Mô hình dữ liệu (`schema_version: "1.1"`, `template: "neoclassical_townhouse"`)

Khối `classic` thay cho `modern` [đề xuất]. Mọi số là `Param` có provenance. Tên trường cuối cùng do người làm plan chốt, nhưng phải đủ các ý sau:

- **`footprint_width`, `footprint_depth`, `wall_thickness`, `slab_thickness`:** như modern.
- **`floors[]`** (1–4): `height`, `openings_front[]`, `openings_rear[]`.
  - Mỗi lỗ cửa có `kind ∈ door | window | door_wood`, và `head ∈ flat | arch` (vòm bán nguyệt, bán kính = rộng/2).
  - Tuỳ chọn: `balcony` (kiểu `iron_belly | balustrade | round_iron`, độ đua, cao lan can), `hood` (mũ phào), `keystone`.
- **`bay`** (khối nhô):
  - `side ∈ left | right`, `width`, `projection` (đua ra trước mặt tiền), tầng `from..to`.
  - `columns` (bật/tắt; số cột 2; bán kính; kiểu đầu cột `leaf`).
  - `pediment` (hồi tam giác nhỏ phía trên khối nhô: độ dốc, có hoa văn đắp không).
  - Khối nhô đua ra trên sân trước nhưng không vượt ranh trước.
  - **Ý nghĩa** [người viết spec chốt]:
    - Ở tầng thấp nhất của khối nhô, mặt trước để trống thành **lô gia**: cột đứng ở mép sàn khối nhô, cửa nằm trên mặt tiền chính phía sau cột. Các tầng trên của khối nhô có tường trước riêng.
    - Lỗ cửa nằm trong khoảng ngang của khối nhô sẽ đặt trên tường trước của khối nhô (tầng kín) hoặc trên mặt tiền chính (tầng lô gia).
    - Phần đua của khối nhô phía trên tầng trệt đóng vai trò ô văng che cửa chính.
    - Hồi nhỏ đặt trên đỉnh khối nhô và được phép nhô lên trong dải tầng kế tiếp, nhưng không chạm lỗ cửa tầng đó.
- **`pilasters`:** bật/tắt, rộng, đua.
- **`cornices`:** phào giữa các tầng và phào mái (cao, đua, `dentils` bật/tắt).
- **`roof`:**
  - `pitch_deg` (25–55), `overhang` (đua mái trước/sau), `ridge` dọc chiều sâu.
  - `gable_front`: `oculus` (bán kính) và `ornament` (bật/tắt).
  - `gutters` (bật/tắt).
- **`front_yard`:** như modern (`kind`, cổng, rào); thêm `gate_style ∈ iron`, `gate_piers` (trụ cổng có đèn).
- **`materials`:** vai trò mới `trim` (chi tiết trắng), `panel` (kem), `roof_tiles` (ngói, texture CC0 `clay_roof_tiles*`), `iron`, `door_wood`, `frame` (khung cửa sẫm). Các vai trò chung (`wall`, `window_glass`, `paving`, `grass`, bối cảnh M2c) giữ nguyên.
- **`context`:** dùng nguyên khối M2c.

**Validate** (thêm vào luật chung):
- Mọi thứ nằm trong lô; khối nhô và ban công không vượt ranh trước.
- Lỗ vòm phải vừa trong tầng: đỉnh vòm + lanh tô ≤ chiều cao thông thuỷ.
- Lỗ cửa không chồng lên cột, trụ ốp hay khối nhô sai chỗ.
- Độ dốc mái trong khoảng 25–55°.
- Hồi nhỏ của khối nhô không đâm vào mái chính.
- Cửa sổ tròn nằm trọn trong hồi.
- Tổng chiều cao (kể cả đỉnh mái) ≤ 25 m.

## 4. Hình học

- **Tường có lỗ vòm thật:**
  - `wall_mesh` hiện chỉ cắt lỗ chữ nhật. Cần một cách tạo tường có lỗ đa giác (vòm bán nguyệt xấp xỉ ≥ 24 đoạn; cửa tròn), thuần Python, kín, test được không cần `bpy`.
  - Người làm plan chọn cách: tam giác hoá đa giác có lỗ, hoặc tách lưới quanh lỗ.
  - Boolean của Blender **không** được dùng trong lõi. Bản thử dùng boolean, nhưng boolean khó test và không tất định.
- **Mái:**
  - Hai tấm mái dốc có độ dày, phủ cả footprint cộng `overhang` trước/sau, mép bên nằm trong ranh lô.
  - Hồi tam giác (tường) ở trước và sau, có phào dốc theo mái.
  - Máng xối là rãnh dọc hai mép bên.
  - Ngói dùng texture có UV theo mét, hướng hàng ngói chạy ngang.
- **Primitive mới** (thuần Python, mỗi primitive có test):
  - `lathe` (tiện tròn: con tiện, thân cột, bệ, đĩa ban công).
  - `sweep` (quét biên dạng phào theo đường trong mặt phẳng tường: phào thẳng, phào dốc, khung vòm, vòng cửa tròn).
  - `leaf` (lá cuộn), `spiral` (cuộn xoắn), `belly_bar` (song sắt phình).
  - Hình học và tham số tham khảo theo bản thử.
- **Gom object:** mỗi thành phần đặt tên là một object (gộp mesh), ví dụ:
  - `Bay_Columns`, `Bay_Pediment`, `Bay_Pediment_Ornament`, `Balcony_F2_Iron`, `Balcony_F2_Balusters`.
  - `Cornice_F1`, `Cornice_Roof`, `Gable_Front`, `Gable_Front_Ornament`, `Oculus_Front`, `Roof_Tiles_L`, `Roof_Tiles_R`, `Gutter_L`, `Gutter_R`, `Pilaster_L`, `Pilaster_R`.
- **Hoa văn:** tất định, không dùng số ngẫu nhiên, hoặc dùng seed cố định. Hoa văn nằm trong khối bao của thành phần chủ ± dung sai và chạm mặt tường (không lơ lửng).
- **Ngân sách** [đề xuất]:
  - ≤ 400 nghìn tam giác cho nhà chính kể cả hoa văn.
  - Render `final` ≤ 40 s/ảnh, VRAM ≤ 3.5 GB (cùng ngưỡng M2c).
  - Vượt ngân sách thì giảm độ mịn hoa văn chứ không bỏ thành phần.

## 5. Fixture demo

Thêm `examples/neoclassical_townhouse/project.json`, ghi "DEMO FIXTURE", mọi số `needs_review`, dựng theo ảnh tham chiếu [đề xuất]:
- **Lô và tầng:**
  - Lô 5 × 20 m; lùi trước 4.0 m; footprint 5 × 14.5 m.
  - 3 tầng (3.6 / 3.4 / 3.4 m) cộng mái dốc 40°, hồi trước có cửa sổ tròn bán kính 0.45 m kèm hoa văn.
- **Tầng trệt:** cửa gỗ 2 cánh rộng 1.8 m, đầu vòm, có ô rẻ quạt; cổng sắt với 2 trụ cổng có đèn; rào sắt.
- **Khối nhô trái** (rộng 2.6 m, đua 0.9 m, chỉ tầng 2) [người viết spec chốt]:
  - Tầng 2 là lô gia: 2 cột đầu lá đứng ở mép sàn khối nhô; cửa vòm trên mặt tiền chính phía sau; ban công cong lan can sắt phình đua thêm ra trước cột.
  - Hồi nhỏ có hoa văn đắp đặt trên đỉnh khối nhô, cao 1.2 m, nhô lên dải tầng 3.
  - Tầng 3 bên trái: cửa chữ nhật, bậu ở 1.3 m (trên đỉnh hồi nhỏ), lan can sắt thẳng.
- **Bên phải:**
  - Tầng 2: cửa sổ chữ nhật với ban công con tiện.
  - Tầng 3: cửa sổ vòm cao với ban công tròn sắt.
- **Chung:** trụ ốp hai góc; phào có răng cưa dưới mái; màu trắng/kem; bối cảnh M2c (đường, hàng xóm, đèn, cây theo luật M2c).

## 6. Kiểm thử

- **Unit:**
  - Schema của template mới, gồm các giá trị sai.
  - Tường có lỗ vòm: kín, không có mặt nằm trong lỗ, diện tích bằng diện tích tường trừ lỗ (±1 mm²).
  - Từng primitive (`lathe`, `sweep`, `leaf`, `spiral`): kích thước và tính tất định.
  - Mái phủ footprint cộng đua, mép trong lô, đúng độ dốc ±0.1°.
  - Hoa văn và cột trong khối bao, chạm tường.
  - Kiểm tra hình học không chồng nhau.
  - Hash golden M1 không đổi; fixture modern cho plan như trước.
- **Integration smoke (Blender thật):** build fixture mẫu C; đủ object đặt tên đúng; ray-cast xuyên lỗ vòm và lỗ tròn; 10 view; `.blend` mở lại được; GLB import lại khớp.
- **Integration có tài sản:** texture ngói có trong `materials/` và `LICENSES.json`.
- **Manual:**
  - Build `final` và benchmark (ghi STATUS).
  - Chủ dự án so ảnh với ảnh tham chiếu.
  - Ghi rõ đây là kiểm tra bằng mắt.

## 7. Để lại cho người làm plan / thi công

- Tên trường chi tiết.
- Cách tam giác hoá tường có lỗ vòm.
- Biên dạng phào cụ thể; số lá, số cuộn.
- Chọn texture ngói cụ thể (`clay_roof_tiles`, `_02` hoặc `_03`) và texture kem.
- Tổ chức module (gợi ý: `geometry/classic_*.py`, `geometry/primitives_classic.py`).
- Cách tách phần dùng chung khỏi `modern_*`.

## 8. Giới hạn đã biết

- Hoa văn ở mức "đọc đúng khi nhìn cả mặt tiền"; nhìn cận thì thô hơn mô hình hoa văn thương mại.
- Một kiểu đầu cột (lá), một kiểu sắt phình.
- Mặt sau đơn giản.
- Mái chỉ có hai mái dốc đỉnh dọc chiều sâu.
- Bối cảnh vẫn mang các giới hạn của M2c: cây gần nhà bị lọc, hàng xóm che góc chéo.

# Exterior AI Agent

Trợ lý dựng hình ảnh **ngoại thất** kiến trúc: tham số đã kiểm tra → một scene Blender duy nhất → 10 ảnh từ 10 góc chuẩn → file `.blend` sửa được, `.glb` và gói giao hàng có checksum.

Trạng thái hiện tại: **M0 + M1 + M2a + M2b** (xem [docs/STATUS.md](docs/STATUS.md)). Chưa có AI, chưa đọc CAD/ảnh, chưa có API/cloud. Nội thất vẫn làm trong JEGA. Chính sách phiên bản: [docs/dependency-policy.md](docs/dependency-policy.md).

> `examples/demo_house/project.json` là **DEMO FIXTURE**, không phải nhà thật. Các giá trị đề xuất (dày tường, lỗ cửa, vật liệu…) được đánh dấu `needs_review`.

## Yêu cầu

- Windows 10/11, PowerShell 5.1 trở lên
- Python **3.13** (có `py` launcher)
- Blender **5.2.2 LTS** (bản zip portable, không cần quyền admin)
- Đủ RAM trống cho Blender (máy 8 GB: nên đóng trình duyệt nặng khi render)

## Cài đặt (PowerShell)

```powershell
cd "C:\Projects\Architecture-ai-agent"
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
```

Nếu `Activate.ps1` bị chặn: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, hoặc gọi thẳng `.\.venv\Scripts\exterior-agent.exe`.

Môi trường được tách biệt: gói Python của dự án nằm trong `.venv`; **Python nhúng của Blender không cài thêm gì** (script Blender chỉ dùng thư viện chuẩn + `bpy`).

### Cài Blender 5.2.2 LTS

```powershell
New-Item -ItemType Directory -Force "C:\Tools" | Out-Null
$zip = Join-Path $env:TEMP "blender-5.2.2-windows-x64.zip"
curl.exe -L --fail -o "$zip" "https://download.blender.org/release/Blender5.2/blender-5.2.2-windows-x64.zip"
(Get-FileHash "$zip" -Algorithm SHA256).Hash
# Phải bằng: 3849D17A682CBA006075AAA3F3597ECB5C9C30EC31035B2E092C53E40679B535
Expand-Archive "$zip" -DestinationPath "C:\Tools"
```

### Cấu hình đường dẫn Blender

```powershell
# Chỉ cho phiên hiện tại:
$env:EXTERIOR_AGENT_BLENDER = "C:\Tools\blender-5.2.2-windows-x64\blender.exe"
# Lưu lâu dài cho user (mở PowerShell mới sau khi chạy):
[Environment]::SetEnvironmentVariable("EXTERIOR_AGENT_BLENDER", "C:\Tools\blender-5.2.2-windows-x64\blender.exe", "User")
```

Thứ tự tìm Blender: `--blender "<đường dẫn>"` → biến `EXTERIOR_AGENT_BLENDER` → `blender` trên `PATH`.

## Lệnh

```powershell
exterior-agent doctor                                              # Python, Blender, GPU, RAM
exterior-agent validate "examples\demo_house\project.json"         # kiểm tra + liệt kê giá trị cần duyệt
exterior-agent build "examples\demo_house\project.json"            # preview: Eevee 1280x720
exterior-agent build "examples\demo_house\project.json" --profile smoke    # 128x72, Cycles CPU (nhanh)
exterior-agent build "examples\demo_house\project.json" --profile final    # 1920x1080, chỉ sau khi duyệt scene
exterior-agent build "examples\demo_house\project.json" --engine cycles --device gpu   # Cycles trên GPU (CUDA)
exterior-agent build "du an\project.json" --out "D:\Ket qua"       # đường dẫn có dấu cách: đặt trong ngoặc kép
.\scripts\check.ps1                                                # ruff, unit, integration, pip-audit
```

Mã thoát: `0` xong, `1` lỗi build, `2` dữ liệu/tuỳ chọn sai hoặc từ chối resume, `3` không tìm thấy Blender, `130` bị huỷ (Ctrl+C).

## Đổi thiết kế

Sao chép `examples\demo_house\project.json` thành file mới, sửa `value` (rộng/sâu/cao, `openings`…), giữ `unit`, `source`, `source_ref`, `status` cho mỗi giá trị. Không cần sửa code.

- Đơn vị chiều dài: `m`, `cm`, `mm`, `ft`, `in` (được quy về mét, giữ bản ghi gốc trong `original`).
- `offset` của lỗ cửa: tính từ **đầu bên trái của mặt đứng khi đứng ngoài nhìn vào bức tường đó** tới mép trái lỗ.
- M1 chỉ hỗ trợ: 1 tầng, mái bằng, `input_mode: "parameters"`, đúng 10 camera chuẩn.

## Template nhà phố hiện đại (M2a)

Fixture: `examples\modern_townhouse\project.json` (`schema_version: "1.1"`, `template: "modern_townhouse"`, DEMO FIXTURE, mọi số đề xuất là `needs_review`).

```powershell
exterior-agent validate "examples\modern_townhouse\project.json"
exterior-agent build "examples\modern_townhouse\project.json"
```

Khối `modern` gồm `floors[]` (1–5 tầng; mỗi tầng `height`, `front_setback` — tầng trên lùi vào tạo terrace, `openings_front`/`openings_rear` với `kind` = `door_4leaf` | `door` | `window`, `terrace_pergola`), `balconies[]`, `frames[]` (khung bao đua ra, hình chữ U ngược), `louvers[]` (lam đứng), `canopy` (ô văng tầng 1), `roof` (tường chắn mái, tum thang, `garden` với bồn cây + pergola) và `front_yard` (`parking` | `garden`, cổng, rào, `car`, `motorbikes`).

Tắt một thành phần: để danh sách rỗng (`"balconies": []`, `"frames": []`, `"louvers": []`), xoá khối (`canopy`, `roof.garden`, `terrace_pergola`), hoặc đặt `car` = `false`, `motorbikes` = `0`. Tổng chiều cao (các tầng + tum thang/tường chắn) tối đa 25 m. Vật liệu hiện là màu phẳng; texture/HDRI là M2b. Project `1.0` (nhà demo M1) vẫn build như cũ.

## Ảnh gần như thật (M2b): tài sản CC0, final, benchmark

Texture, bầu trời HDRI và mô hình cây lấy từ Poly Haven (**CC0**), ghim bằng sha256 trong `assets\catalog.json`. Tải một lần vào cache ngoài git (mặc định `C:\Tools\exterior-agent-assets`, đổi bằng `$env:EXTERIOR_AGENT_ASSETS`):

```powershell
exterior-agent assets fetch                     # tải + kiểm sha256; chạy lại chỉ tải file thiếu/hỏng
exterior-agent doctor                           # dòng "Assets" cho biết còn thiếu bao nhiêu file
exterior-agent build "examples\modern_townhouse\project.json" --profile final     # Cycles GPU (CUDA), 128 samples, khử nhiễu
exterior-agent build "examples\modern_townhouse\project.json" --profile final --samples 64
exterior-agent benchmark "examples\modern_townhouse\project.json" --samples 64,128,256,512   # thời gian/VRAM/RAM từng mức
```

- Vật liệu chọn texture bằng `"texture": "<asset id>"` trong `materials.<vai trò>.value`; màu `base_color` nhân với texture (để `[1, 1, 1]` nếu muốn giữ nguyên màu texture). Bầu trời: khối `world` (`hdri`, `strength`, `rotation_deg`). Cây trên mái: `roof.garden.plant_models`.
- Chỉ project `modern_townhouse` dùng tài sản; profile `smoke` và nhà demo M1 luôn màu phẳng, không cần cache.
- Gói giao có thêm `materials\<asset>\...` (chỉ file đã dùng) và `materials\LICENSES.json`; `delivery.json` liệt kê `assets` (CC0) và `placeholders` (xe/xe máy là khối mẫu). `.blend` dùng đường dẫn tương đối `//materials/...` nên chép cả thư mục revision sang máy khác vẫn mở được.
- Thiếu tài sản → build dừng trước Blender với thông báo chạy `exterior-agent assets fetch`. GPU hết bộ nhớ → thông báo gợi ý giảm `--samples`/cây hoặc `--engine cycles --device cpu`.
- `benchmark` ghi `output\benchmarks\<project_id>\<thời điểm>\benchmark.json` và ảnh từng mức (`s64\`, `s128\`…), mỗi lần chỉ một Blender.

## Kết quả

Mỗi lần build tạo thư mục mới, **không bao giờ ghi đè**:

```
output\<project_id>\r<project_revision>-<hash8>\
  model.blend          # scene sửa được: Wall_*, Roof_Slab, Opening_*, Door_*, Window_*, Site_*, CAM_*, MAT_*
  model.glb
  images\01_front.png … 10_aerial.png
  contact_sheet.png    # lưới 5 x 2 có nhãn
  project.json         # tham số đã chuẩn hoá về mét
  scene_plan.json      # hình học + camera đã tính
  delivery.json        # phiên bản, cấu hình render, giá trị cần duyệt, checksum từng file
  job.json             # trạng thái, thời gian từng bước/từng ảnh
  logs\build.log, logs\render.log
```

`hash8` đổi khi tham số hoặc cấu hình render đổi → chạy lại với tham số mới luôn ra thư mục mới.

## Huỷ, lỗi và chạy tiếp

- Ctrl+C dừng Blender, đánh dấu `cancelled`, giữ ảnh đã xong. Chạy lại **đúng lệnh cũ** để render tiếp các ảnh còn thiếu.
- Chỉ chạy tiếp khi phiên bản Blender/tool, cấu hình render, tham số và checksum `model.blend`/`model.glb` còn khớp. Nếu `model.blend` đã bị sửa tay, công cụ **từ chối** để không ghi đè; xoá thư mục đó hoặc tăng `project_revision`.
- Revision đã `completed` chạy lại sẽ không làm gì.
- Chỉ dọn file tạm đã biết: `*.tmp`, `*.tmp.blend`, `*.tmp.glb`, `*.blend1`, `images\.tmp_*.png`.

## Kiểm tra GLB bằng viewer độc lập (thủ công)

Exporter báo thành công là chưa đủ. Mở `model.glb` bằng một viewer khác Blender, ví dụ https://gltf-viewer.donmccurdy.com/ (kéo thả file; viewer xử lý trong trình duyệt). Kiểm tra: kích thước nhà 4.5 × 12 × 3.75 m, tường có lỗ cửa thật, vật liệu có màu, tên node `Wall_Front`… Ghi kết quả vào `docs/STATUS.md` là **manual**.

## Giới hạn

- Nhà demo M1: một tầng, mái bằng. Template hiện đại: 1–5 tầng mái bằng, texture CC0 + HDRI (M2b); xe/xe máy vẫn là khối mẫu (Poly Haven không có mô hình xe CC0); nền xung quanh là mặt phẳng xám trơn.
- Chưa đọc DXF/ảnh/phác thảo; chưa có AI, API, cloud.
- OptiX không chạy trên driver NVIDIA hiện tại của laptop; `--device gpu` dùng CUDA trước. Eevee/GPU chưa được kiểm trên CI.
- Không hứa hiệu năng hay 4K; số đo thời gian xem `docs/STATUS.md`.

## Xử lý sự cố

| Triệu chứng | Cách xử lý |
| --- | --- |
| `ERROR Blender not found` (mã 3) | Đặt `EXTERIOR_AGENT_BLENDER` hoặc `--blender "C:\...\blender.exe"`; kiểm tra bằng `exterior-agent doctor` |
| `ERROR <đường dẫn>: ...` (mã 2) | Sửa giá trị trong `project.json` theo đường dẫn báo lỗi |
| `resume refused` | Thư mục revision đã bị sửa hoặc khác phiên bản; xoá thư mục đó hoặc tăng `project_revision` |
| Render Eevee lỗi | Thử `--engine cycles` (CPU); xem `logs\render.log` |
| `--device gpu` lỗi | Cập nhật driver NVIDIA hoặc dùng `--engine cycles --device cpu` |
| Máy chậm / hết RAM | Đóng ứng dụng khác (benchmark đo được chỉ còn 0.08 GB RAM trống lúc bắt đầu render mức đầu tiên); dùng `--profile smoke` để thử nhanh; chỉ chạy một build mỗi lần |
| `asset file(s) missing or corrupt` | Chạy `exterior-agent assets fetch` (cần mạng lần đầu) |

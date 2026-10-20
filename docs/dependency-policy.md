# Chính sách phụ thuộc và phiên bản

## Python của dự án (host)

- Python **3.13** (`requires-python = ">=3.13,<3.14"` trong `pyproject.toml`).
- `pyproject.toml` khai báo phụ thuộc trực tiếp với khoảng phiên bản; `requirements.lock` ghim **chính xác** mọi gói, kể cả gói bắc cầu.
- Cài đặt luôn từ lock: `python -m pip install -r requirements.lock` rồi `python -m pip install -e . --no-deps`.
- Nâng cấp có chủ đích: sửa `pyproject.toml` nếu cần → `.\scripts\lock.ps1` (venv sạch tạm thời) → `.\scripts\check.ps1` → commit lock cùng thay đổi.
- `pip-audit -r requirements.lock` chạy trong `check.ps1` và CI.

## Blender

- Ghim **Blender 5.2.2 LTS**. SHA256 bản chính thức:
  - Windows zip: `3849d17a682cba006075aaa3f3597ecb5c9c30ec31035b2e092c53e40679b535`
  - Linux tar.xz (CI): `84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168`
- Python nhúng của Blender (3.13.13) **không cài thêm gói**. Script trong `src/exterior_agent/blender/scripts/` chỉ dùng thư viện chuẩn, `bpy`, `mathutils`.
- Đổi phiên bản Blender: kiểm lại mọi API `bpy` trên đúng bản mới, cập nhật SHA256 ở `scripts/install_blender_ci.sh`, README, tài liệu này, rồi chạy đủ test integration. `delivery.json` và fingerprint resume ghi phiên bản Blender, nên revision cũ không bị trộn với bản mới.

## Tài sản CC0 (texture, HDRI, mô hình)

- Chỉ dùng tài sản **CC0** của Poly Haven (https://polyhaven.com/license). Mỗi file ghim URL, kích thước và **sha256** trong `assets/catalog.json` (commit); file thật nằm trong cache ngoài git.
- Thêm/đổi tài sản: `python scripts/pin_assets.py <id>:<texture|hdri|model>:<1k|2k>` (đối chiếu md5 của Poly Haven, tính sha256), rồi `exterior-agent assets fetch` và chạy lại kiểm tra. Không sửa tay sha256.
- Chỉ tải qua HTTPS từ `dl.polyhaven.org`; đường dẫn file phải là đường dẫn tương đối an toàn. Không chạy hay import gì từ file tải về.

## GitHub Actions

- Mọi action ghim theo **SHA commit đầy đủ**, có comment ghi tag (`# v7.0.1`).
- Workflow chỉ có `permissions: contents: read`; `persist-credentials: false`.
- Nâng cấp action: tra SHA của tag mới từ repo chính thức, cập nhật cả SHA và comment.

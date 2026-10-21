# Cài đặt trên máy Windows

Yêu cầu: AmiBroker (đã thử với 5.60 32-bit) có bản quyền, database `D:\AmiBroker_VN\Data` được cập nhật EOD hằng ngày (`CapNhat.bat`), Python 3.11+, Git.

## 1. Lấy mã nguồn và thư viện

```bat
git clone https://github.com/nguyenworkingg-sketch/Amibroker D:\AmiBroker_Hub
cd D:\AmiBroker_Hub
python -m pip install -r exporter\requirements.txt
```

Đường dẫn khác mặc định? Sửa `settings` trong `exporter\strategy_config.yaml` hoặc đặt biến môi trường theo `.env.example`.

## 2. Cài AFL adapter

```bat
python exporter\install_afl.py
```

Chép `amibroker\afl\Hub_*.afl` vào `C:\Program Files (x86)\AmiBroker\Formulas\Hub`. Không sửa file AFL gốc nào.

## 3. Đăng nhập GitHub một lần (không lưu token trong repo)

```bat
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
```

Thông tin đăng nhập được Windows Credential Manager giữ. Không đặt token vào file cấu hình.

## 4. Chạy thử

```bat
python exporter\run_explorations.py
```

* Mở AmiBroker (hoặc để script tự mở), chạy lần lượt các Exploration, ghi `archive\raw\<phiên>\*.csv`, cập nhật `data\`.
* Kết quả từng bước ở cuối màn hình và trong `archive\logs\hub_<ngày>.log`; trang **System Status** hiển thị lại sau khi publish.
* Mã thoát: 0 thành công · 1 lỗi một phần · 2 thất bại · 3 hoãn vì AmiBroker đang bận.

Tái tạo lịch sử cho các phương pháp hỗ trợ (VCP, Wyckoff, Pullback, Rotation, bảng ngành):

```bat
python exporter\run_explorations.py --backfill 250
```

## 5. Đẩy lên GitHub

```bat
python exporter\publish.py --dry-run
python exporter\publish.py
```

Chỉ commit thư mục `data\`. Push lỗi (mất mạng…) thì commit vẫn ở máy, lần sau đẩy tiếp.

## 6. Lịch tự động

```bat
powershell -ExecutionPolicy Bypass -File scheduler\install_task.ps1
```

Tạo task **“AmiBroker VN - Exploration Hub”** 08:30 thứ 2–6, chạy `scheduler\HubChay.bat` (= `run_explorations.py --publish --wait-minutes 30`). Đổi giờ: thêm `-Time 09:00`.

Khuyến nghị thêm vào cuối `D:\AmiBroker_VN\TuDong_CapNhat.bat` (lịch 16:00) để web có kết quả ngay chiều đó:

```bat
if not errorlevel 1 call "D:\AmiBroker_Hub\scheduler\HubChay.bat" >> "%~dp0logs\capnhat_%D%.log" 2>&1
```

Máy phải bật và đăng nhập Windows (khóa màn hình vẫn chạy). Bỏ lỡ giờ → task chạy bù khi máy bật lại. Máy tắt nhiều ngày → web vẫn hiện dữ liệu cũ kèm cảnh báo.

## 7. Bật GitHub Pages (một lần)

Repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**. Workflow `.github/workflows/deploy.yml` sẽ test + build + deploy mỗi lần `main` có commit mới.

## Nhập tay (chưa dùng COM)

AmiBroker: Analysis → chọn file `Formulas\Hub\Hub_VCP.afl` (hoặc Explorer gốc có đủ cột) → Explore → chuột phải bảng → **Export** → CSV.

```bat
python exporter\import_csv.py --strategy VCP --file D:\exports\vcp.csv
python exporter\import_csv.py --strategy RS --file D:\exports\rs.csv --session 2026-10-16
python exporter\publish.py
```

## Analysis Project (.apx)

Nếu anh/chị lưu một Analysis Project (File → Save As trong cửa sổ Analysis), điền đường dẫn vào `apx:` của phương pháp đó. Exporter sẽ dùng `AnalysisDocs.Open → Run(1) → chờ IsBusy → Export` thay cho file adapter. Cột xuất ra phải khớp `columns` trong cấu hình.

## Xử lý sự cố

| Thông báo | Cách xử lý |
|---|---|
| `AmiBroker co nen cuoi … khac phien EOD` | Database có nến trong phiên (DNSE) hoặc chưa cập nhật. Chờ `CapNhat.bat` chạy xong rồi chạy lại |
| `Dang chay: dnse_live.py …` | Bộ cập nhật trong phiên đang chạy; exporter tự chờ (`--wait-minutes`) rồi hoãn |
| `Chua cai file AFL` | Chạy `python exporter\install_afl.py` |
| `empty_suspicious` | 0 mã đạt trong khi phiên trước có nhiều → kiểm tra AmiBroker; nếu đúng là 0, chạy lại với `--allow-empty` |
| `Push that bai` | Kiểm tra mạng / `gh auth status`; dữ liệu đã commit cục bộ |

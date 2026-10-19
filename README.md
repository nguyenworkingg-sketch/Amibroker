# AmiBroker Exploration Hub

Bảng điều khiển hằng ngày tổng hợp kết quả **Exploration của AmiBroker** cho cổ phiếu Việt Nam (tầm nắm giữ 1–3 tháng).
Trang web trả lời câu hỏi:

> **Hôm nay các phương pháp Exploration của tôi đang phát hiện những cổ phiếu nào, tín hiệu nào mới xuất hiện, phương pháp nào đang đồng thuận, và lịch sử những tín hiệu này ra sao?**

🌐 Website: **https://nguyenworkingg-sketch.github.io/Amibroker/**

Đây **không** phải hệ thống đặt lệnh hay quản lý danh mục. Kết quả lọc theo quy tắc kỹ thuật, không phải khuyến nghị đầu tư.

## Kiến trúc

```
AmiBroker (Hub_*.afl gọi các Core AFL gốc)        máy Windows, có bản quyền + database
   │  OLE/COM (pywin32): LoadFormula → [Scan] → Explore → Export CSV
   ▼
exporter/ (Python)  kiểm tra → chuẩn hóa → snapshot theo phiên → JSON cho web
   │  git commit data/ + push (chỉ thư mục data/)
   ▼
GitHub ── Actions: test + build ──► GitHub Pages (React, trang tĩnh, đọc JSON)
```

Website **không** kết nối tới AmiBroker; máy Windows tắt thì web vẫn hiện lần đồng bộ thành công gần nhất kèm cảnh báo dữ liệu cũ.
Chi tiết: [docs/architecture.md](docs/architecture.md).

## Các phương pháp (strategy registry)

| ID | Tên | AFL gốc (logic giữ nguyên) | Đạt khi | Tái tạo lịch sử |
|---|---|---|---|---|
| VCP | Nền co hẹp biến động | `VCP_Core.afl` / `VCP_Explorer.afl` | trạng thái Forming / Pre-Breakout / Breakout + thanh khoản | Có |
| WYCKOFF | Wyckoff tích lũy | `Wyckoff_VN_core.afl` / `Wyckoff_VN_Screener.afl` | “Tất cả ứng viên tích lũy” | Có |
| PULLBACK | Trend Pullback | `TrendPullback_core.afl` / `TrendPullback_Scanner.afl` | “Ưu tiên S3–S6” (mặc định Scanner) | Có |
| RS | Relative Strength | `Xep hang - Sieu song.afl` (rổ PTKT 108 mã) | RS Rating ≥ 80 | Không (chỉ phiên cuối) |
| ROTATION | Sector Rotation | `PTKT_core.afl › PtktSector` | ngành mạnh hơn VNINDEX + mã mạnh hơn ngành và tăng tốc — **quy tắc mới của Hub, chưa backtest** | Có |
| HIGH_BETA | High Beta | `HighBeta_Exploration.afl` | Composite ≥ 70 (chế độ “Elite + Strong”) | Không (chỉ phiên cuối) |

Thêm phương pháp mới: thêm một mục trong [`exporter/strategy_config.yaml`](exporter/strategy_config.yaml) — frontend tự hiển thị. Xem [docs/strategy-registry.md](docs/strategy-registry.md).

## Cài đặt trên máy Windows chạy AmiBroker

Xem đầy đủ: [docs/setup-windows.md](docs/setup-windows.md). Tóm tắt:

```bat
git clone https://github.com/nguyenworkingg-sketch/Amibroker D:\AmiBroker_Hub
cd D:\AmiBroker_Hub
python -m pip install -r exporter\requirements.txt
python exporter\install_afl.py                 :: chép Hub_*.afl vào Formulas\Hub
python exporter\run_explorations.py            :: chạy thử 1 lần (không đẩy lên GitHub)
python exporter\run_explorations.py --backfill 250   :: tái tạo ~1 năm lịch sử (VCP, Wyckoff, Pullback, Rotation, ngành)
powershell -ExecutionPolicy Bypass -File scheduler\install_task.ps1   :: lịch 08:30 thứ 2–6
```

Chưa thiết lập COM? Dùng **nhập tay**: trong AmiBroker chạy Exploration → chuột phải bảng kết quả → Export → rồi

```bat
python exporter\import_csv.py --strategy VCP --file D:\exports\vcp.csv
python exporter\publish.py
```

## Lệnh thường dùng

| Lệnh | Việc |
|---|---|
| `python exporter\run_explorations.py [--publish] [--strategies VCP,RS] [--backfill N]` | Chạy Exploration qua COM, chuẩn hóa, dựng JSON |
| `python exporter\import_csv.py --strategy ID --file x.csv [--session YYYY-MM-DD] [--range]` | Nhập tay CSV (cùng bộ kiểm tra) |
| `python exporter\normalize_data.py` | Dựng lại toàn bộ JSON từ snapshot (tất định) |
| `python exporter\publish.py [--dry-run]` | Commit + push thư mục `data/` |
| `python exporter\import_backtest.py --strategy ID --file trades.csv` | Nhập danh sách lệnh backtest AmiBroker |
| `python -m unittest discover -s tests` | Kiểm thử exporter |
| `cd frontend && npm run dev` | Chạy web cục bộ (http://localhost:5173/Amibroker/) |

## Dữ liệu & dữ liệu công bố

* `data/snapshots/<phiên>/<ID>.json` — kết quả **gốc đã chuẩn hóa** của từng phương pháp mỗi phiên (lưu vết, kiểm tra lại được).
* `data/sessions`, `history`, `tickers`, `market`, `performance`, `meta.json`, `status.json` — file dựng sẵn cho web.
* Schema: [docs/data-contract.md](docs/data-contract.md).
* **Không** đưa lên repo: file xuất gốc, chuỗi giá OHLCV, log, khóa (`archive/` bị `.gitignore`). Web chỉ chứa giá đóng cửa và lợi suất của **mã đạt bộ lọc** tại phiên tín hiệu cùng các chỉ số dẫn xuất.
  Dữ liệu giá gốc lấy từ nguồn công khai (SSI/VNDirect/DNSE) — anh/chị nên kiểm tra điều khoản của nhà cung cấp trước khi mở rộng phần công bố.
* Không có token, mật khẩu hay danh mục cá nhân nào trong repo.

## Trung thực về dữ liệu

* Thiếu dữ liệu → `null` / “—”, không bao giờ ép thành 0.
* Lịch sử “tái tạo” = chạy lại Exploration trên dữ liệu quá khứ (giá đã điều chỉnh, danh sách ngành hiện tại) — được gắn nhãn riêng với dữ liệu “chạy thật”.
* “Không còn đạt” ≠ tín hiệu bán. Xếp hạng đồng thuận không phải dự báo lợi nhuận, chưa kiểm định ngoài mẫu.

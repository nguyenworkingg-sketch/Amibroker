# Danh mục phương pháp (strategy registry)

Nguồn: [`exporter/strategy_config.yaml`](../exporter/strategy_config.yaml). Frontend đọc danh mục qua `data/meta.json` nên **không cần sửa code web** khi thêm phương pháp.

## Trường của một phương pháp

| Trường | Ý nghĩa |
|---|---|
| `id` | Mã duy nhất (VIẾT HOA), dùng trong tên file snapshot |
| `name_vi`, `description` | Tên và mô tả tiếng Việt hiển thị trên web |
| `enabled` | `false` = không chạy, vẫn giữ lịch sử |
| `version` | Phiên bản quy tắc; đổi khi đổi logic/tham số (ghi vào mỗi snapshot) |
| `afl` | File adapter trong `Formulas\Hub` (cài bằng `install_afl.py`) |
| `source_afl` | File AFL gốc chứa logic (để tra cứu) |
| `apx` | (tuỳ chọn) đường dẫn Analysis Project `.apx`. Có file → chạy bằng `AnalysisDocs.Open → Run(1) → IsBusy → Export` thay cho `afl` |
| `apply_to` | `all` hoặc `watchlist:N` |
| `two_pass` | `true` = cần Scan trước Explore (xếp hạng cắt ngang bằng static var) |
| `supports_backfill` | `true` = adapter tính theo từng phiên, chạy được Range From–To |
| `columns` | Tên cột trong file xuất: `ticker`, `score` (bắt buộc), `date`, `state_code`, `state` |
| `pass_rule` | (tuỳ chọn) quy tắc đạt áp dụng ở exporter, ví dụ `{column: RS Rating, op: ">=", value: 80}` |
| `score_name`, `scoring` | Tên và cách tính điểm (hiển thị) |
| `state_labels` | Nhãn tiếng Việt theo `StateCode` |
| `metrics` | Cột riêng: `col` (tên trong CSV), `key` (khóa JSON), `label`, `unit` (`text`, `bool`, `%`, …) |

## Thêm một phương pháp mới

1. Viết `amibroker/afl/Hub_<TEN>.afl`: `#include` Core của anh/chị, đặt `Filter` = điều kiện đạt, xuất tối thiểu `Ticker`, `DateNum` (nếu tính theo phiên) và `Score`.
2. Thêm mục vào `strategy_config.yaml`.
3. `python exporter\install_afl.py` rồi `python exporter\run_explorations.py --strategies <TEN>`.
4. Kiểm tra trên trang **System Status**, sau đó `--publish`.

Không báo cáo một phương pháp là “đã kết nối” khi chưa chạy thật trên AmiBroker: trường `connected` trong `meta.json` chỉ `true` khi có snapshot thật (không phải mô phỏng).

## Ghi chú từng phương pháp

* **VCP** — đạt = trạng thái 1–3 (bỏ Failed/Extended khỏi danh sách “đạt” để theo dõi trạng thái mới/tiếp diễn có ý nghĩa). Hạng = thứ tự Quality Score.
* **WYCKOFF** — đạt = mọi giai đoạn tích lũy (Tạo nền → LPS). Lọc giai đoạn cụ thể bằng cột “Trạng thái” trên web.
* **PULLBACK** — giống bộ lọc mặc định của Scanner (S3–S6, đủ thanh khoản).
* **RS** — rổ “PTKT 108 mã” (watchlist 0) như bảng Xếp hạng hiện tại; RS Rating là hạng cắt ngang nên chỉ có từ ngày Hub bắt đầu chạy.
* **ROTATION** — quy tắc mới của Hub (version 0.1), chưa backtest; chỉ áp dụng cho ~230 mã thuộc 19 nhóm ngành PTKT.
* **HIGH_BETA** — chạy nguyên `HighBeta_Exploration.afl`, đạt khi Composite ≥ 70; hạng gốc trong toàn rổ lưu ở `market_rank_native`.
* **RSZ** — tín hiệu tự so với lịch sử của mã (z-score), độc lập với RS Rating. Backtest 01/2014–10/2026 (`D:\AmiBroker_VN\backtest\bt_rsz.py`, `ket_qua_rsz.txt`): so với mua ngẫu nhiên mã thanh khoản cùng cách mua + phí, mỗi kiểu vào (từ Suy yếu / từ Cải thiện) chỉ tốt hơn ở 1 trong 2 giai đoạn (2014–2021 / 2022–2026); các đặc điểm xu hướng (cách MA50/MA200, đỉnh 1 năm, ExRet-Z) đảo chiều giữa 2 giai đoạn. Dùng làm danh sách theo dõi, không dùng riêng để giao dịch.

## RS chung trên web

Cột “RS” (0–100) trên mọi bảng **không** phải RS Rating của PTKT. Nó là phân vị lợi suất 63 phiên của mã trong toàn bộ cổ phiếu HOSE/HNX/UPCoM có đủ dữ liệu, do exporter tính từ file EOD, để mọi mã đều có cùng một thước đo.

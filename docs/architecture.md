# Kiến trúc

## Luồng dữ liệu

```
AmiBroker 5.60 (Windows, database D:\AmiBroker_VN\Data)
  └─ Formulas\Hub\Hub_*.afl  ── #include các Core AFL gốc (không sửa logic)
        │  OLE/COM: Broker.Application → Analysis.LoadFormula → [Scan] → Explore → Export
        ▼
exporter/run_explorations.py  (tiến trình cha: khóa, kiểm tra xung đột, timeout)
  ├─ hub/amibroker.py   mỗi Exploration chạy trong 1 tiến trình con (python -m hub.amibroker) → timeout cứng
  ├─ hub/csvio.py       đọc CSV: mã hóa (UTF-8/1258/1252), dấu phân cách, dấu thập phân, giá trị thiếu
  ├─ hub/normalize.py   kiểm tra cột, quy tắc đạt, chống trùng, xếp hạng → snapshot
  ├─ hub/market.py      làm giàu từ file EOD (giá, lợi suất, GTGD20, RS), độ rộng, hiệu suất sau tín hiệu
  ├─ hub/store.py       ghi snapshot nguyên tử, chống trùng, chống rỗng bất thường, lưu bản cũ
  ├─ hub/derive.py      dựng toàn bộ JSON cho web từ snapshot (tất định)
  └─ publish.py         git add data/ → commit → pull --rebase → push (không force)
        ▼
GitHub repo (main) ── .github/workflows/deploy.yml: unittest + lint + tsc + vitest + build → Pages
        ▼
https://nguyenworkingg-sketch.github.io/Amibroker/  (React + Vite + Tailwind + TanStack Table + Recharts)
```

## Vì sao có file `Hub_*.afl`

* Logic sàng lọc nằm trong các **Core** (`VCP_Core.afl`, `TrendPullback_core.afl`, `Wyckoff_VN_core.afl`, `PTKT_core.afl`, `HighBeta_Core.afl`). Adapter chỉ gọi Core và xuất **bộ cột chuẩn** (`Ticker, DateNum, StateCode, State, Score` + cột riêng).
* Adapter dùng **mảng theo từng phiên** (không `LastValue`) → chạy *Range From–To* để tái tạo lịch sử; ở phiên cuối kết quả trùng với Explorer gốc.
* Adapter nằm ở đường dẫn riêng nên Analysis dùng **tham số mặc định trong code**, không phụ thuộc tham số anh/chị đang chỉnh tay trên Explorer gốc.
* RS và High Beta xếp hạng cắt ngang toàn rổ bằng static var (Scan → Explore), chỉ tính được phiên cuối → adapter `#include` nguyên file gốc; quy tắc đạt áp dụng ở exporter.
* `Hub_Rotation.afl` là **quy tắc mới** ghép từ chỉ báo có sẵn (`PtktSector`) — được ghi rõ “chưa backtest”.

## An toàn vận hành

| Rủi ro | Biện pháp |
|---|---|
| Hai thao tác AmiBroker cùng lúc | Khóa `archive/hub.lock` (PID); hoãn nếu đang chạy `dnse_live.py`, `vn_data.py`, `import_amibroker.js`, `CapNhat.bat`… (`--wait-minutes`) |
| Nến trong phiên chưa chốt | So ngày nến cuối VNINDEX trong AmiBroker với file EOD; phiên = hôm nay mà chưa qua 15:30 → từ chối |
| Gán nhầm ngày | Ngày phiên lấy từ dữ liệu EOD (không phải ngày lịch); dòng có ngày sau phiên → file bị loại |
| Exploration treo | Timeout cứng ở tiến trình cha (mặc định 1.200 giây), không thử lại khi quá thời gian |
| File lỗi/rỗng thay dữ liệu tốt | Thiếu cột → `invalid`; 0 mã khi phiên trước ≥ 5 mã → `empty_suspicious`, giữ nguyên dữ liệu cũ |
| Ghi dở dang | Ghi file tạm rồi `os.replace` (nguyên tử) |
| Chạy lại trùng | So `content_hash`: không đổi → không ghi, không commit |
| Tái tạo đè dữ liệu thật | Snapshot `backfill` không bao giờ ghi đè `live`/`manual` |
| Lộ bí mật | Chỉ commit `data/`; xác thực bằng Git Credential Manager; không token trong repo |

Exporter **không ghi** vào database AmiBroker (chỉ Scan/Explore/Export).

## Lịch

* `scheduler\install_task.ps1` → “AmiBroker VN - Exploration Hub” 08:30 thứ 2–6 (dùng dữ liệu EOD phiên đã hoàn tất gần nhất).
* `D:\AmiBroker_VN\TuDong_CapNhat.bat` (18:00) gọi thêm `scheduler\HubChay.bat` sau khi chốt số liệu thành công → web có kết quả ngay tối đó. Lần 08:30 hôm sau thấy dữ liệu không đổi thì không commit.
* Mốc thời gian được tách bạch: **phiên giao dịch** (`session`), **dữ liệu đến** (`data_asof`), **lúc chạy Exploration** (`generated_at`), **lúc xuất bản** (`status.last_publication.at`).

# Hợp đồng dữ liệu (data contract)

Mọi file là JSON UTF-8. Thiếu dữ liệu = `null` (không bao giờ ép thành 0). Ngày theo ISO `YYYY-MM-DD` (phiên giao dịch, giờ Việt Nam). Thời điểm theo ISO 8601 có múi giờ `+07:00`.

## Đơn vị

| Trường | Đơn vị |
|---|---|
| `close`, `pivot`, `stop` | nghìn đồng (như database AmiBroker) |
| `ret_1d`, `ret_5d`, `ret_20d`, `*_pct` | % (đã nhân 100) |
| `avg_trading_value_20` | tỷ đồng / phiên, bình quân 20 phiên giao dịch (phiên không giao dịch tính 0 đồng) |
| `relative_strength_score` | 0–100, phân vị lợi suất 63 phiên toàn thị trường |
| `strategy_score` | thang riêng của từng phương pháp (xem `score_name`) — **không so sánh giữa các phương pháp** |
| `strategy_rank` | 1 = điểm cao nhất trong danh sách đạt của phương pháp ở phiên đó; cùng điểm cùng hạng |

## Snapshot — `data/snapshots/<session>/<STRATEGY_ID>.json`

Bản ghi gốc của một phương pháp tại một phiên. Đây là nguồn để dựng lại mọi file khác.

```json
{
  "schema_version": 1,
  "meta": {
    "strategy_id": "VCP", "strategy_version": "1.0",
    "session": "2026-10-16", "data_asof": "2026-10-16",
    "generated_at": "2026-10-16T18:21:05+07:00",
    "origin": "live | backfill | manual | demo",
    "source_file": "VCP_daily_182105.csv", "source_sha256": "…",
    "pass_rule": null, "record_count": 42, "content_hash": "…", "revision": 1, "warnings": []
  },
  "records": [{
    "ticker": "FPT", "strategy_id": "VCP", "signal_date": "2026-10-16",
    "state_code": 2, "state": "Pre-Breakout",
    "strategy_score": 81.5, "strategy_rank": 1,
    "name": "FPT Corp", "exchange": "HOSE", "sector": "Công nghệ",
    "close": 58.2, "ret_1d": 0.34, "ret_5d": 0.52, "ret_20d": -10.71,
    "avg_trading_value_20": 319.5, "relative_strength_score": 48.5,
    "additional_metrics": {"base_days": 40, "dist_pivot_pct": 2.1}
  }]
}
```

Định danh tín hiệu = (`strategy_id`, `ticker`, `signal_date`). `content_hash` = SHA-256 của `records` (không gồm thời điểm chạy) → cùng đầu vào cho cùng hash.

## File dựng cho web

| File | Nội dung |
|---|---|
| `meta.json` | Danh mục phương pháp (+ trạng thái kết nối, phiên gần nhất), danh sách phiên, cờ `demo` |
| `status.json` | Nhật ký 60 lần chạy, trạng thái từng phương pháp, `last_success`, `last_publication` |
| `latest/summary.json` | Thống kê từng phiên: số mã, mới, tiếp diễn, quay lại, không còn đạt, ≥2, ≥3, theo phương pháp |
| `sessions/<date>.json` | Toàn bộ bản ghi của phiên (đã gắn `signal_status`, `previous_rank`, `rank_change`, `streak`, `episode_start`, `first_seen`, `n_strategies`, `strategies`, `multi_streak`) + `dropped` + `benchmark` |
| `history/index.json` | Bảng (cột + dòng) theo (phương pháp, mã): lần đầu, gần nhất, số phiên, chuỗi hiện tại, số lần quay lại |
| `tickers/<T>.json` | Dòng thời gian từng mã: `[điểm, hạng, trạng thái, nhãn]` theo phương pháp, RS, giá; các đợt tín hiệu + hiệu suất sau tín hiệu |
| `market/breadth.json` | % mã trên MA20/50/200, tăng/giảm, đỉnh 52 tuần — ALL/HOSE/HNX/UPCoM |
| `market/sectors.json` | Bảng ngành (RS-Z, RS-Mom, góc RRG, hạng, Δ hạng) + lịch sử 130 phiên |
| `market/signal_trend.json` | Số mã đạt theo phương pháp mỗi phiên |
| `performance/forward.json` | Hiệu suất sau tín hiệu theo phương pháp × kỳ hạn (5/10/20/40/60 phiên): gộp, sau phí, VN-Index, vượt trội |
| `backtest/index.json` | Báo cáo backtest đã nhập (nếu có) |

## Trạng thái tín hiệu

So với **phiên có dữ liệu liền trước của cùng phương pháp** (theo lịch phiên giao dịch). Nếu giữa hai lần có phiên bị thiếu, `strategies[ID].gap` > 1 và web ghi chú.

| Mã | Nghĩa |
|---|---|
| `NEW` | Đạt hôm nay, không đạt phiên trước, chưa từng đạt trước đó |
| `RETURNING` | Đạt hôm nay, không đạt phiên trước, đã từng đạt |
| `CONTINUING` | Đạt cả phiên trước và hôm nay |
| `DROPPED` | Đạt phiên trước, hôm nay không còn (không phải tín hiệu bán) |
| `UNKNOWN` | Phiên đầu tiên của phương pháp — chưa có phiên để so sánh |

## Hiệu suất sau tín hiệu

* Chỉ đợt `NEW`/`RETURNING` (không đếm lặp phiên tiếp diễn).
* Vào = giá **mở cửa phiên kế tiếp** sau ngày tín hiệu; ra = giá đóng cửa phiên thứ *h* tính từ phiên vào. VN-Index cùng cửa sổ.
* Sau phí = gộp − 0,6% (phí mua 0,15% + phí/thuế bán 0,25% + trượt giá 0,1% × 2).
* Cửa sổ chưa đủ → `null` (“chờ”). Giá đã điều chỉnh theo dữ liệu EOD hiện tại.

## Đọc CSV

`hub/csvio.py`: thử UTF-8 (có/không BOM) → Windows-1258 → Windows-1252; chuẩn hóa Unicode NFC; nhận dấu phân cách `,` `;` tab; dấu thập phân `.` hoặc `,`; tên cột không phân biệt hoa thường/khoảng trắng; `""`, `-`, `{EMPTY}`, `N/A`, Null nội bộ của AmiBroker (`-1e10`) → `null`. Ngày nhận `DateNum` AmiBroker (`1261016`), `YYYYMMDD`, `YYYY-MM-DD`, `DD/MM/YYYY`.

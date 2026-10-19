# Dữ liệu mẫu (MÔ PHỎNG)

Các file trong thư mục này là **dữ liệu mô phỏng** để kiểm thử và minh họa định dạng file nhập tay.
Mã cổ phiếu đều có tiền tố `DEMO` và không phải cổ phiếu thật. Các con số được đặt tay, không lấy từ AmiBroker.

| File | Định dạng giống | Dùng để |
|---|---|---|
| `demo_vcp_explore.csv` | `Hub_VCP.afl` chạy Range From–To (nhiều phiên, có cột `DateNum`) | Kiểm thử nhập tay nhiều phiên (`--range`) |
| `demo_rs_explore.csv` | `Xep hang - Sieu song.afl` (không có cột ngày, cần `--session`) | Kiểm thử quy tắc đạt `RS Rating >= 80` |

Ví dụ: nhập vào một thư mục tạm, đánh dấu là mô phỏng:

```
python exporter\import_csv.py --strategy VCP --file exporter\samples\demo_vcp_explore.csv --range --session 2026-10-16 --no-market --origin demo --data-dir %TEMP%\hub_demo
```

Khi `--origin demo`, website hiện băng **"Dữ liệu mô phỏng"** trên mọi trang.

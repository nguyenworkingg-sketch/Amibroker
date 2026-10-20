"""Tai phan nganh ICB (VNDirect finfo) cho toan thi truong -> exporter/reference/icb_sectors.csv.

    python exporter\\fetch_icb.py

File tham chieu duoc commit vao repo (phan nganh la thong tin cong khai). Chay lai khi muon cap nhat (vd moi quy).
Cot: Ticker, icb4_code, icb4, icb3, icb2 (ten tieng Viet theo VNDirect).
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "reference" / "icb_sectors.csv"
URL = "https://api-finfo.vndirect.com.vn/v4/industry_classification?q=industryLevel:{lv}&size=500"


def get(u: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
        return json.loads(r.read())


def main() -> int:
    names: dict[int, dict[str, str]] = {}
    member: dict[int, dict[str, str]] = {}
    for lv in (2, 3, 4):
        names[lv], member[lv] = {}, {}
        for r in get(URL.format(lv=lv))["data"]:
            code = r["industryCode"]
            names[lv][code] = (r.get("vietnameseName") or r.get("englishName") or code).strip()
            for t in (r.get("codeList") or "").split(","):
                t = t.strip().upper()
                if t:
                    member[lv].setdefault(t, code)
    rows = []
    for t in sorted(member[4]):
        c4 = member[4][t]
        rows.append({"Ticker": t, "icb4_code": c4, "icb4": names[4].get(c4, ""),
                     "icb3": names[3].get(member[3].get(t, ""), ""), "icb2": names[2].get(member[2].get(t, ""), "")})
    if len(rows) < 1000:
        print(f"Chi co {len(rows)} ma - nghi loi API, khong ghi de file cu", file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Da ghi {len(rows)} ma -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

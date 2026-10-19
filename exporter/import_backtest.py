"""Nhap ket qua backtest tu DANH SACH LENH xuat tu AmiBroker (Backtest -> Report -> Trade list -> Export CSV).

    python exporter\\import_backtest.py --strategy VCP --file trades.csv --initial-equity 1000000000 --title "VCP STOP 2018-2026"

Chi so tinh tu file (khong tu bia): so lenh, ty le thang, lai/lo TB moi lenh (%), so phien nam giu TB, profit factor.
Neu co --initial-equity va cot "Cum. Profit": CAGR va Max Drawdown tinh tren von tai cac thoi diem dong lenh
(xap xi, ghi ro). Sharpe va Exposure de trong (null) vi danh sach lenh khong co chuoi von theo ngay.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub.config import load_config  # noqa: E402
from hub.csvio import parse_num, read_table  # noqa: E402
from hub.util import iso, now_vn, parse_date, read_json, sha256_file, write_json  # noqa: E402


def metrics_from_trades(path: Path, initial_equity: float | None) -> tuple[dict, str]:
    t = read_table(path)
    col = {k: t.col_index(k) for k in ("Symbol", "Date", "Ex. date", "% Profit", "Profit", "# bars", "Cum. Profit")}
    for need in ("Symbol", "Date", "Ex. date", "% Profit"):
        if col[need] is None:
            raise ValueError(f"Thieu cot '{need}' - can file Trade list xuat tu AmiBroker. Tieu de: {t.header}")
    pct, prof, bars, exits = [], [], [], []
    starts = []
    for r in t.rows:
        p = parse_num(r[col["% Profit"]], t.decimal)
        if p is None:
            continue
        pct.append(p)
        if col["Profit"] is not None:
            v = parse_num(r[col["Profit"]], t.decimal)
            if v is not None:
                prof.append(v)
        if col["# bars"] is not None:
            b = parse_num(r[col["# bars"]], t.decimal)
            if b is not None:
                bars.append(b)
        d0, d1 = parse_date(r[col["Date"]]), parse_date(r[col["Ex. date"]])
        if d0:
            starts.append(d0)
        if d1 and col["Cum. Profit"] is not None:
            cp = parse_num(r[col["Cum. Profit"]], t.decimal)
            if cp is not None:
                exits.append((d1, cp))
    if not pct:
        raise ValueError("Khong co lenh nao doc duoc")
    gains = sum(x for x in (prof or pct) if x > 0)
    losses = -sum(x for x in (prof or pct) if x < 0)
    m = {"trades": len(pct), "win_rate": round(100 * sum(1 for x in pct if x > 0) / len(pct), 2),
         "avg_trade": round(statistics.fmean(pct), 3), "avg_bars": round(statistics.fmean(bars), 1) if bars else None,
         "profit_factor": round(gains / losses, 3) if losses > 0 else None,
         "cagr": None, "max_drawdown": None, "sharpe": None, "exposure": None}
    end = max(d for d, _ in exits) if exits else None
    start = min(starts) if starts else None
    if initial_equity and exits and start:
        exits.sort()
        eq = [initial_equity + cp for _, cp in exits]
        years = max((exits[-1][0] - start).days / 365.25, 1e-9)
        if eq[-1] > 0:
            m["cagr"] = round(100 * ((eq[-1] / initial_equity) ** (1 / years) - 1), 2)
        peak, mdd = initial_equity, 0.0
        for e in eq:
            peak = max(peak, e)
            mdd = min(mdd, e / peak - 1)
        m["max_drawdown"] = round(100 * mdd, 2)
    period = f"{start.isoformat() if start else '?'} → {end.isoformat() if end else '?'}"
    return m, period


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--title")
    ap.add_argument("--initial-equity", type=float)
    a = ap.parse_args()
    cfg = load_config()
    s = cfg.strategy(a.strategy)
    path = Path(a.file)
    m, period = metrics_from_trades(path, a.initial_equity)
    idx_path = cfg.data_dir / "backtest" / "index.json"
    doc = read_json(idx_path, {"available": True, "reports": []})
    rid = f"{s.id}_{sha256_file(path)[:10]}"
    doc["reports"] = [r for r in doc["reports"] if r["id"] != rid] + [{
        "id": rid, "strategy_id": s.id, "title": a.title or f"{s.name_vi} – {path.stem}", "source": path.name,
        "period": period, "imported_at": iso(now_vn()), "metrics": m,
        "notes": "CAGR/MaxDD xap xi tren von tai thoi diem dong lenh" if m["cagr"] is not None else None}]
    doc["available"] = True
    write_json(idx_path, doc, compact=False)
    print(f"Da nhap {m['trades']} lenh ({period}) -> {idx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

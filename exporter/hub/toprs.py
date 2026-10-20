"""TOP RS: danh sach co phieu dang nam trong nhom suc manh tuong doi cao cua TOAN THI TRUONG.

Dinh nghia (cau hinh trong strategy_config.yaml > top_rs):
  * Ro moi phien: ma HOSE/HNX/UPCoM CO GIAO DICH phien do va GTGD TB20 >= min_value_bil (mac dinh 2 ty).
  * SM trung han = RS Rating (1-99): cung cong thuc PTKT_core.afl > PtktPerfW / PtktRank:
        perf = (0.4 r63 + 0.2 r126 + 0.2 r189 + 0.2 r252)(co phieu) / (cung cong thuc)(VNINDEX)
        rating = round((so ma nho hon + (so ma bang + 1)/2) / n * 98 + 1)   (= hang trung binh / n * 98 + 1)
  * SM ngan han = cung cach xep hang tren loi suat vuot VNINDEX 20 phien.
  * VAO top khi SM trung han >= enter (90 ~ top 10%); CHI ROI top khi < exit (80) -> vung dem tranh ra/vao lien tuc.
    Phien ma khong duoc xep hang (khong giao dich / GTGD20 duoi nguong) -> giu nguyen trang thai, nhung qua
    10 phien lien tiep khong duoc xep hang -> roi top (ly do "roi ro thanh khoan").
  * Gia vao top = gia dong cua phien vao top; loi suat tu khi vao = gia hien tai / gia vao - 1 (gia DA DIEU CHINH).
Chi dung du lieu den tung phien (khong nhin truoc). Tinh lai toan bo moi lan tu chuoi gia AmiBroker (tat dinh).
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from .config import EXPORTER_DIR, Config
from .util import clean_number, write_json


def _perf_w(c: pd.DataFrame | pd.Series):
    r = {n: c / c.shift(n) for n in (63, 126, 189, 252)}
    r[126] = r[126].fillna(r[63])
    r[189] = r[189].fillna(r[126])
    r[252] = r[252].fillna(r[189])
    return 0.4 * r[63] + 0.2 * r[126] + 0.2 * r[189] + 0.2 * r[252]


def rating_frame(values: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Xep hang cat ngang tung phien (1-99) trong ro; ngoai ro -> NaN."""
    v = values.where(universe)
    rk = v.rank(axis=1, method="average")          # = so nho hon + (so bang + 1) / 2
    n = v.notna().sum(axis=1)
    return np.floor(rk.div(n, axis=0) * 98 + 1 + 0.5)  # round() cua AFL: lam tron nua len


def load_icb(cfg: Config) -> dict[str, dict]:
    p = Path(cfg.settings.get("top_rs", {}).get("icb_file", "reference/icb_sectors.csv"))
    if not p.is_absolute():
        p = EXPORTER_DIR / p
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return {r["Ticker"]: r for r in csv.DictReader(f)}


def compute(market, enter: float = 90, exit_: float = 80, min_value: float = 2.0, short_n: int = 20,
            warmup: int = 252, max_unranked: int = 10) -> dict:
    """-> dict voi cac DataFrame: mid, short, universe, va danh sach dot top (episodes)."""
    cf = market.cf
    bench = market.bench_close
    universe = market.traded & (market.adv20 >= min_value)
    perf = _perf_w(cf).div(_perf_w(bench), axis=0)
    mid = rating_frame(perf.where(cf.notna()), universe & perf.notna())
    ex_s = (cf / cf.shift(short_n)).div(bench / bench.shift(short_n), axis=0)
    short = rating_frame(ex_s, universe & ex_s.notna())
    dates = list(mid.index)
    start = min(warmup, len(dates) - 1)
    state: dict[str, dict] = {}
    episodes: list[dict] = []
    cols = list(mid.columns)
    M = mid.to_numpy()
    for i in range(start, len(dates)):
        row = M[i]
        for j, t in enumerate(cols):
            r = row[j]
            ep = state.get(t)
            if np.isnan(r):
                # khong duoc xep hang (ngung GD / GTGD20 duoi nguong): giu trang thai toi da max_unranked phien
                if ep is not None and i - ep["last_ranked"] > max_unranked:
                    ep.update({"exit_i": i, "exit_reason": "illiquid"})
                    episodes.append(ep)
                    del state[t]
                continue
            if ep is None:
                if r >= enter:
                    state[t] = {"ticker": t, "entry_i": i, "censored": i == start, "last_ranked": i}
            elif r < exit_:
                ep.update({"exit_i": i, "exit_reason": "rs"})
                episodes.append(ep)
                del state[t]
            else:
                ep["last_ranked"] = i
    return {"mid": mid, "short": short, "universe": universe, "dates": dates, "start": start,
            "open": list(state.values()), "closed": episodes}


def _w_last(c: np.ndarray) -> np.ndarray:
    """PtktPerfW tai phien CUOI cua ma tran gia (phien x ma), co fallback 126/189/252 nhu AFL."""
    last = c[-1]
    r = {}
    for n in (63, 126, 189, 252):
        r[n] = last / c[-1 - n] if c.shape[0] > n else np.full(c.shape[1], np.nan)
    r[126] = np.where(np.isnan(r[126]), r[63], r[126])
    r[189] = np.where(np.isnan(r[189]), r[126], r[189])
    r[252] = np.where(np.isnan(r[252]), r[189], r[252])
    return 0.4 * r[63] + 0.2 * r[126] + 0.2 * r[189] + 0.2 * r[252]


def intraday_estimate(market, doc: dict, live: dict[str, float], bench_live: float, icb: dict | None = None) -> dict:
    """Uoc tinh RS Rating hom nay = chuoi gia da chot + gia tam hom nay (ma khong co gia tam: giu gia hom qua).
    Ro = ro cua phien da chot gan nhat. -> {enters, exits, coverage, universe}"""
    rule = doc["rule"]
    enter, exit_ = float(rule["enter"]), float(rule["exit"])
    last = len(market.calendar) - 1
    univ = [t for t in market.cf.columns if bool(market.traded[t].iloc[last]) and (market.adv20[t].iloc[last] or 0) >= rule["min_value_bil"]]
    base = market.cf[univ].to_numpy()
    today = np.array([live.get(t, base[-1, j]) for j, t in enumerate(univ)])
    c = np.vstack([base, today])
    b = np.append(market.bench_close.to_numpy(), bench_live)[:, None]
    perf = _w_last(c) / _w_last(b)[0]
    sn = int(rule.get("short_sessions", 20))
    short = (c[-1] / c[-1 - sn]) / (b[-1, 0] / b[-1 - sn, 0])
    ok = ~np.isnan(perf)
    def rate(v, mask):
        s = pd.Series(np.where(mask, v, np.nan))
        return (np.floor(s.rank(method="average") / s.notna().sum() * 98 + 1 + 0.5)).to_numpy()
    mid_r = rate(perf, ok)
    short_r = rate(short, ~np.isnan(short))
    in_top = {r["ticker"] for r in doc.get("rows", [])}
    icb = icb or {}
    enters, exits = [], []
    for j, t in enumerate(univ):
        if t not in live or np.isnan(mid_r[j]):
            continue  # chi canh bao ma co gia that trong phien
        row = {"ticker": t, "sector": (icb.get(t) or {}).get("icb4"), "sm_mid": float(mid_r[j]),
               "sm_short": None if np.isnan(short_r[j]) else float(short_r[j]), "price": float(today[j]), "exit": exit_}
        if t not in in_top and mid_r[j] >= enter:
            enters.append(row)
        elif t in in_top and mid_r[j] < exit_:
            exits.append(row)
    enters.sort(key=lambda r: -r["sm_mid"])
    exits.sort(key=lambda r: r["sm_mid"])
    return {"enters": enters, "exits": exits, "universe": len(univ), "coverage": sum(1 for t in univ if t in live)}


def build(cfg: Config, market, out_dir: Path) -> int:
    """Ghi data/toprs/latest.json. Tra ve so file thay doi."""
    st = cfg.settings.get("top_rs", {})
    enter, exit_ = float(st.get("enter", 90)), float(st.get("exit", 80))
    min_value = float(st.get("min_value_bil", 2.0))
    res = compute(market, enter, exit_, min_value, int(st.get("short_sessions", 20)))
    icb = load_icb(cfg)
    dates, cf, bench = res["dates"], market.cf, market.bench_close
    last = len(dates) - 1
    d = lambda i: dates[i].date().isoformat()  # noqa: E731

    def common(t: str, i0: int, i1: int) -> dict:
        p0, p1 = cf[t].iloc[i0], cf[t].iloc[i1]
        b0, b1 = bench.iloc[i0], bench.iloc[i1]
        ret = (p1 / p0 - 1) * 100 if p0 and not np.isnan(p0) and not np.isnan(p1) else None
        bret = (b1 / b0 - 1) * 100
        seg = cf[t].iloc[i0:i1 + 1]
        g = icb.get(t, {})
        return {"ticker": t, "name": market.names.get(t) or None, "exchange": market.exchange.get(t),
                "sector": g.get("icb4") or None, "sector_l3": g.get("icb3") or None,
                "entry_date": d(i0), "entry_price": clean_number(p0, 3), "price": clean_number(p1, 3),
                "ret_pct": clean_number(ret, 2), "vni_ret_pct": clean_number(bret, 2),
                "excess_pct": clean_number(None if ret is None else ret - bret, 2),
                "max_ret_pct": clean_number((seg.max() / p0 - 1) * 100 if p0 else None, 2),
                "sessions": i1 - i0 + 1}

    rows = []
    for ep in res["open"]:
        t, i0 = ep["ticker"], ep["entry_i"]
        r = common(t, i0, last)
        r.update({"entry_censored": ep["censored"], "new_today": i0 == last,
                  "sm_short": clean_number(res["short"][t].iloc[last], 0), "sm_mid": clean_number(res["mid"][t].iloc[last], 0),
                  "sm_mid_entry": clean_number(res["mid"][t].iloc[i0], 0),
                  "avg_trading_value_20": clean_number(market.adv20[t].iloc[last], 2),
                  "ranked_today": bool(res["universe"][t].iloc[last])})
        rows.append(r)
    rows.sort(key=lambda r: (r["entry_date"], r["ticker"]), reverse=True)
    exits = []
    for ep in res["closed"]:
        if ep["exit_i"] >= last - 19:
            r = common(ep["ticker"], ep["entry_i"], ep["exit_i"])
            r.update({"exit_date": d(ep["exit_i"]), "entry_censored": ep["censored"], "exit_reason": ep.get("exit_reason"),
                      "sm_mid_exit": clean_number(res["mid"][ep["ticker"]].iloc[ep["exit_i"]], 0)})
            exits.append(r)
    exits.sort(key=lambda r: (r["exit_date"], r["ticker"]), reverse=True)
    # tong ket chi tinh ma co NGAY VAO THAT (bo ma da o top tu truoc ngay bat dau theo doi)
    rets = [r["ret_pct"] for r in rows if r["ret_pct"] is not None and not r["entry_censored"]]
    exs = [r["excess_pct"] for r in rows if r["excess_pct"] is not None and not r["entry_censored"]]
    # chuoi so ma trong top theo phien (120 phien cuoi)
    count = {}
    for ep in res["open"] + res["closed"]:
        for i in range(ep["entry_i"], ep.get("exit_i", last + 1)):
            count[i] = count.get(i, 0) + 1
    series = [{"date": d(i), "in_top": count.get(i, 0),
               "new": sum(1 for ep in res["open"] + res["closed"] if ep["entry_i"] == i and not ep["censored"]),
               "exits": sum(1 for ep in res["closed"] if ep["exit_i"] == i),
               "universe": int(res["universe"].iloc[i].sum())} for i in range(max(res["start"], last - 119), last + 1)]
    doc = {
        "available": True, "session": d(last), "tracking_since": d(res["start"]),
        "rule": {"enter": enter, "exit": exit_, "min_value_bil": min_value, "short_sessions": int(st.get("short_sessions", 20))},
        "summary": {"universe": int(res["universe"].iloc[last].sum()), "in_top": len(rows),
                    "censored": sum(1 for r in rows if r["entry_censored"]), "measured": len(rets),
                    "new_today": sum(1 for r in rows if r["new_today"]),
                    "exits_today": sum(1 for r in exits if r["exit_date"] == d(last)),
                    "pct_positive": clean_number(100 * sum(1 for x in rets if x > 0) / len(rets), 1) if rets else None,
                    "avg_ret_pct": clean_number(float(np.mean(rets)), 2) if rets else None,
                    "median_ret_pct": clean_number(float(np.median(rets)), 2) if rets else None,
                    "avg_excess_pct": clean_number(float(np.mean(exs)), 2) if exs else None},
        "rows": rows, "recent_exits": exits, "series": series,
    }
    # danh sach ma trong ro -> bo cap nhat trong phien (DNSE) lay gia cho ca ro (canh bao trong phien)
    wl = st.get("live_watchlist_file")
    if wl:
        univ = sorted(t for t in res["universe"].columns if bool(res["universe"][t].iloc[last]))
        try:
            Path(wl).write_text("# Ro Top RS (GTGD20 >= %.0f ty) - Hub ghi moi toi, dung cho canh bao trong phien\n" % min_value
                                + "\n".join(univ) + "\n", encoding="utf-8")
        except OSError:
            pass
    return int(write_json(out_dir / "toprs" / "latest.json", doc))

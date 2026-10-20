"""Dung toan bo file JSON cho website TU cac snapshot (tat dinh: cung snapshot + cung du lieu gia -> cung file).

Trang thai tin hieu (so voi phien co du lieu TRUOC DO cua cung chien luoc, theo lich phien giao dich):
  NEW        dat hom nay, khong dat phien truoc, chua tung dat truoc do
  RETURNING  dat hom nay, khong dat phien truoc, nhung da tung dat truoc do (quay lai)
  CONTINUING dat ca phien truoc va hom nay
  DROPPED    dat phien truoc, hom nay khong con dat (KHONG phai tin hieu ban)
  UNKNOWN    phien dau tien cua chien luoc -> chua co phien truoc de so sanh
"""
from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from pathlib import Path

from .config import Config
from .store import list_snapshots
from .util import clean_number, dumps, read_json, sha256_text, write_json

QUADRANT = {(True, True): "Dẫn dắt", (True, False): "Suy yếu", (False, False): "Tụt hậu", (False, True): "Cải thiện"}


def _load_all(cfg: Config) -> tuple[dict[str, dict[str, dict]], dict[str, dict]]:
    """-> (snap[sid][session] = snapshot, sectors[session] = aux snapshot)"""
    ids = {s.id for s in cfg.strategies}
    snaps: dict[str, dict[str, dict]] = defaultdict(dict)
    sectors: dict[str, dict] = {}
    for session, sid, path in list_snapshots(cfg):
        if sid == "_SECTORS":
            sectors[session] = read_json(path)
        elif sid in ids:
            snaps[sid][session] = read_json(path)
    return snaps, sectors


def compute_statuses(snaps: dict[str, dict[str, dict]], gap_fn=None) -> dict[str, dict[str, dict]]:
    """-> st[sid][session] = {compared_to, gap, records{ticker: rec+status}, dropped[...]}"""
    out: dict[str, dict[str, dict]] = {}
    for sid, by_s in snaps.items():
        sess = sorted(by_s)
        ever: set[str] = set()
        streak: dict[str, int] = {}
        start: dict[str, str] = {}
        first: dict[str, str] = {}
        prev_recs: dict[str, dict] = {}
        out[sid] = {}
        for k, s in enumerate(sess):
            cur = {r["ticker"]: r for r in by_s[s]["records"]}
            prev_s = sess[k - 1] if k > 0 else None
            recs = {}
            for t, r in cur.items():
                r = dict(r)
                if prev_s is None:
                    stt = "UNKNOWN"
                elif t in prev_recs:
                    stt = "CONTINUING"
                elif t in ever:
                    stt = "RETURNING"
                else:
                    stt = "NEW"
                streak[t] = streak.get(t, 0) + 1 if t in prev_recs else 1
                if t not in prev_recs:
                    start[t] = s
                first.setdefault(t, s)
                pr = prev_recs.get(t, {}).get("strategy_rank")
                rr = r.get("strategy_rank")
                r.update({"signal_status": stt, "previous_rank": pr,
                          "rank_change": (pr - rr) if (pr is not None and rr is not None) else None,
                          "streak": streak[t], "episode_start": start[t], "first_seen": first[t]})
                recs[t] = r
            dropped = []
            if prev_s is not None:
                for t, r in prev_recs.items():
                    if t not in cur:
                        dropped.append({"ticker": t, "strategy_id": sid, "signal_status": "DROPPED", "last_signal_date": prev_s,
                                        "previous_rank": r.get("strategy_rank"), "strategy_score": r.get("strategy_score"),
                                        "state": r.get("state"), "streak": r.get("streak"), "episode_start": r.get("episode_start"),
                                        "name": r.get("name"), "exchange": r.get("exchange"), "sector": r.get("sector")})
                        streak.pop(t, None)
            gap = gap_fn(prev_s, s) if (gap_fn and prev_s) else None
            out[sid][s] = {"compared_to": prev_s, "gap": gap, "records": recs,
                           "dropped": sorted(dropped, key=lambda x: x["ticker"])}
            ever.update(cur)
            prev_recs = recs
    return out


def _forward_for(market, cfg: Config, ticker: str, d: str) -> dict:
    if market is None:
        return {}
    cost = float(cfg.settings.get("round_trip_cost_pct", 0.6))
    res = {}
    for h in cfg.settings.get("forward_horizons", [5, 10, 20, 40, 60]):
        f = market.forward(ticker, dt.date.fromisoformat(d), int(h), cost)
        res[str(h)] = f
    return res


def _summ(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "median": None, "win_rate": None}
    return {"n": len(values), "mean": round(statistics.fmean(values), 3), "median": round(statistics.median(values), 3),
            "win_rate": round(100.0 * sum(1 for v in values if v > 0) / len(values), 1)}


def build_site(cfg: Config, market=None, *, build_time: str | None = None, demo: bool = False) -> dict:
    """Ghi toan bo data/latest, data/sessions, data/history, data/tickers, data/market, data/performance, data/meta.json."""
    dd = cfg.data_dir
    if market is not None and not getattr(market, "enough_history", True):
        raise ValueError(f"Lich su gia chi co {len(market.calendar)} phien (nguon: {getattr(market, 'source', '?')}) -> khong dung lai du lieu web "
                         "de tranh xoa do rong thi truong / hieu suat sau tin hieu. Chay run_explorations.py de lay gia tu AmiBroker.")
    snaps, sectors = _load_all(cfg)
    gap_fn = (lambda a, b: market.session_gap(dt.date.fromisoformat(a), dt.date.fromisoformat(b))) if market else None
    st = compute_statuses(snaps, gap_fn)
    all_sessions = sorted({s for by in snaps.values() for s in by})
    written = 0

    # ---------------------------------------------------------------- tung phien
    multi_streak: dict[str, int] = {}
    prev_multi: set[str] = set()
    session_index = []
    signal_trend = []
    for s in all_sessions:
        per_ticker: dict[str, list[str]] = defaultdict(list)
        records, dropped, strat_info = [], [], {}
        for strat in cfg.strategies:
            info = st.get(strat.id, {}).get(s)
            if info is None:
                strat_info[strat.id] = {"available": False}
                continue
            recs = list(info["records"].values())
            for r in recs:
                per_ticker[r["ticker"]].append(strat.id)
            cnt = defaultdict(int)
            for r in recs:
                cnt[r["signal_status"]] += 1
            meta = snaps[strat.id][s]["meta"]
            strat_info[strat.id] = {"available": True, "compared_to": info["compared_to"], "gap": info["gap"],
                                    "origin": meta["origin"], "generated_at": meta["generated_at"], "data_asof": meta["data_asof"],
                                    "total": len(recs), "new": cnt["NEW"], "returning": cnt["RETURNING"],
                                    "continuing": cnt["CONTINUING"], "unknown": cnt["UNKNOWN"], "dropped": len(info["dropped"])}
            records.extend(recs)
            dropped.extend(info["dropped"])
        cur_multi = {t for t, v in per_ticker.items() if len(v) >= 2}
        for t in list(multi_streak):
            if t not in cur_multi:
                multi_streak.pop(t)
        for t in cur_multi:
            multi_streak[t] = multi_streak.get(t, 0) + 1 if t in prev_multi else 1
        prev_multi = cur_multi
        order = [x.id for x in cfg.strategies]
        for r in records:
            combo = sorted(per_ticker[r["ticker"]], key=order.index)
            r["n_strategies"] = len(combo)
            r["strategies"] = combo
            r["multi_streak"] = multi_streak.get(r["ticker"], 0)
        records.sort(key=lambda r: (order.index(r["strategy_id"]), r["strategy_rank"] if r["strategy_rank"] is not None else 1e9, r["ticker"]))
        bench = market.benchmark_returns(dt.date.fromisoformat(s)) if market else {}
        doc = {"session": s, "benchmark": bench, "strategies": strat_info, "records": records,
               "dropped": sorted(dropped, key=lambda x: (order.index(x["strategy_id"]), x["ticker"]))}
        written += write_json(dd / "sessions" / f"{s}.json", doc)
        avail = [k for k, v in strat_info.items() if v.get("available")]
        uniq = set(per_ticker)
        summary = {
            "session": s,
            "strategies_available": avail,
            "unique_tickers": len(uniq),
            "new": sum(v.get("new", 0) for v in strat_info.values()),
            "returning": sum(v.get("returning", 0) for v in strat_info.values()),
            "continuing": sum(v.get("continuing", 0) for v in strat_info.values()),
            "unknown": sum(v.get("unknown", 0) for v in strat_info.values()),
            "dropped": sum(v.get("dropped", 0) for v in strat_info.values()),
            "multi2": sum(1 for v in per_ticker.values() if len(v) >= 2),
            "multi3": sum(1 for v in per_ticker.values() if len(v) >= 3),
            "by_strategy": {k: {kk: v[kk] for kk in ("total", "new", "returning", "continuing", "unknown", "dropped", "origin")}
                            for k, v in strat_info.items() if v.get("available")},
        }
        session_index.append(summary)
        signal_trend.append({"session": s, **{k: v.get("total") for k, v in strat_info.items() if v.get("available")},
                             "unique": len(uniq), "new": summary["new"] + summary["returning"], "dropped": summary["dropped"]})

    # ---------------------------------------------------------------- lich su + hieu suat sau tin hieu
    hist_rows = []
    perf: dict[str, dict[str, dict[str, list]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    pending: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    tick: dict[str, dict] = {}
    for strat in cfg.strategies:
        by = st.get(strat.id, {})
        sess = sorted(by)
        if not sess:
            continue
        last_s = sess[-1]
        agg: dict[str, dict] = {}
        for s in sess:
            for t, r in by[s]["records"].items():
                a = agg.setdefault(t, {"first": s, "last": s, "n": 0, "episodes": 0, "scores": []})
                a["last"] = s
                a["n"] += 1
                if r["signal_status"] in ("NEW", "RETURNING", "UNKNOWN"):
                    a["episodes"] += 1
                tk = tick.setdefault(t, {"ticker": t, "name": r.get("name"), "exchange": r.get("exchange"), "sector": r.get("sector"),
                                         "timeline": defaultdict(dict), "episodes": [], "rs": {}, "close": {}})
                tk["name"] = r.get("name") or tk["name"]
                tk["exchange"] = r.get("exchange") or tk["exchange"]
                tk["sector"] = r.get("sector") or tk["sector"]
                tk["timeline"][s][strat.id] = [r.get("strategy_score"), r.get("strategy_rank"), r["signal_status"], r.get("state")]
                if r.get("relative_strength_score") is not None:
                    tk["rs"][s] = r["relative_strength_score"]
                if r.get("close") is not None:
                    tk["close"][s] = r["close"]
                if r["signal_status"] in ("NEW", "RETURNING"):
                    fw = _forward_for(market, cfg, t, s)
                    ep = {"strategy_id": strat.id, "start": s, "status": r["signal_status"], "score": r.get("strategy_score"),
                          "origin": snaps[strat.id][s]["meta"]["origin"], "forward": fw}
                    tk["episodes"].append(ep)
                    for h, f in fw.items():
                        if f is None:
                            pending[strat.id][h] += 1
                        else:
                            for k in ("gross", "net", "bench", "excess"):
                                perf[strat.id][h][k].append(f[k])
        for t, a in sorted(agg.items()):
            cur = by[last_s]["records"].get(t)
            hist_rows.append([strat.id, t, a["first"], a["last"], a["n"], cur["streak"] if cur else 0,
                              max(0, a["episodes"] - 1), cur.get("strategy_score") if cur else None,
                              cur.get("strategy_rank") if cur else None, 1 if cur else 0])
    written += write_json(dd / "history" / "index.json", {
        "columns": ["strategy_id", "ticker", "first_signal", "last_signal", "sessions", "current_streak",
                    "reappearances", "current_score", "current_rank", "active"],
        "rows": hist_rows})

    # ticker files
    tdir = dd / "tickers"
    keep = set()
    for t, tk in sorted(tick.items()):
        tl = [{"date": s, "s": tk["timeline"][s]} for s in sorted(tk["timeline"])]
        doc = {"ticker": t, "name": tk["name"], "exchange": tk["exchange"], "sector": tk["sector"], "timeline": tl,
               "rs": [[s, v] for s, v in sorted(tk["rs"].items())], "close": [[s, v] for s, v in sorted(tk["close"].items())],
               "episodes": sorted(tk["episodes"], key=lambda e: (e["start"], e["strategy_id"]))}
        written += write_json(tdir / f"{t}.json", doc)
        keep.add(f"{t}.json")
    if tdir.exists():
        for f in tdir.glob("*.json"):
            if f.name not in keep:
                f.unlink()

    horizons = [str(h) for h in cfg.settings.get("forward_horizons", [5, 10, 20, 40, 60])]
    perf_doc = {"entry_rule": "Vào lệnh = giá mở cửa phiên kế tiếp sau ngày tín hiệu; thoát = giá đóng cửa phiên thứ h tính từ phiên vào.",
                "cost_pct": cfg.settings.get("round_trip_cost_pct", 0.6), "horizons": horizons,
                "available": market is not None, "strategies": {}}
    for strat in cfg.strategies:
        rows = {}
        for h in horizons:
            v = perf[strat.id][h]
            rows[h] = {"gross": _summ(v["gross"]), "net": _summ(v["net"]), "bench": _summ(v["bench"]),
                       "excess": _summ(v["excess"]), "pending": pending[strat.id][h]}
        perf_doc["strategies"][strat.id] = rows
    written += write_json(dd / "performance" / "forward.json", perf_doc)

    # ---------------------------------------------------------------- thi truong + nganh
    if market is not None and all_sessions:
        dates = [d for d in market.sessions() if d.isoformat() >= (all_sessions[0] if len(all_sessions) > 1 else "0000")][-260:]
        written += write_json(dd / "market" / "breadth.json", {"series": market.breadth(dates)})
    written += write_json(dd / "market" / "signal_trend.json", {"series": signal_trend})
    if market is not None:
        from .toprs import build as build_toprs
        written += build_toprs(cfg, market, dd)
    elif not (dd / "toprs" / "latest.json").exists():
        written += write_json(dd / "toprs" / "latest.json", {"available": False})
    written += _build_sectors(cfg, sectors, session_index and all_sessions[-1], st, snaps)

    # ---------------------------------------------------------------- meta + tong quan
    latest = all_sessions[-1] if all_sessions else None
    strat_meta = []
    for strat in cfg.strategies:
        by = snaps.get(strat.id, {})
        last = max(by) if by else None
        m = by[last]["meta"] if last else None
        p = strat.public()
        p.update({"connected": bool(by) and not demo, "last_session": last,
                  "last_generated_at": m["generated_at"] if m else None,
                  "last_count": m["record_count"] if m else None,
                  "sessions_recorded": len(by),
                  "first_session": min(by) if by else None})
        strat_meta.append(p)
    meta = {"schema_version": 1, "demo": demo, "latest_session": latest,
            "sessions": list(reversed(all_sessions)), "strategies": strat_meta,
            "liquidity_default_bil": cfg.settings.get("liquidity_default_bil", 2.0),
            "built_at": build_time, "has_market_data": market is not None,
            "sector_names": sorted(set(cfg.sector_names.values()))}
    written += write_json(dd / "meta.json", meta)
    written += write_json(dd / "latest" / "summary.json", {"latest": session_index[-1] if session_index else None,
                                                           "sessions": list(reversed(session_index))})
    return {"sessions": len(all_sessions), "files_changed": written}


def _build_sectors(cfg: Config, sectors: dict[str, dict], latest: str | None, st, snaps) -> int:
    dd = cfg.data_dir
    if not sectors:
        return write_json(dd / "market" / "sectors.json", {"available": False, "latest": None, "rows": [], "history": {}})
    sess = sorted(sectors)
    def table(s):
        rows = []
        for r in sectors[s]["records"]:
            z, m = r.get("rsz"), r.get("rsmom")
            q = QUADRANT[(z > 0, m > 0)] if (z is not None and m is not None) else None
            rows.append({**r, "quadrant": q})
        ranked = sorted([x for x in rows if x.get("rsz") is not None], key=lambda x: (-x["rsz"], x["sector"]))
        for i, x in enumerate(ranked, 1):
            x["rank"] = i
        return {x["sector"]: x for x in rows}
    last_s = sess[-1]
    cur = table(last_s)
    prev = table(sess[-2]) if len(sess) > 1 else {}
    prev5 = table(sess[-6]) if len(sess) > 5 else {}
    # dem co phieu dat theo nganh x chien luoc (phien moi nhat co tin hieu)
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    sig_s = latest
    for sid, by in st.items():
        info = by.get(sig_s) if sig_s else None
        if not info:
            continue
        for r in info["records"].values():
            if r.get("sector"):
                counts[r["sector"]][sid] += 1
    rows = []
    for name, x in sorted(cur.items(), key=lambda kv: (kv[1].get("rank") or 99, kv[0])):
        rows.append({**x, "prev_rank": prev.get(name, {}).get("rank"), "rank_5": prev5.get(name, {}).get("rank"),
                     "signals": dict(counts.get(name, {})), "signals_total": sum(counts.get(name, {}).values())})
    hist = defaultdict(list)
    for s in sess[-130:]:
        tb = table(s)
        for name, x in tb.items():
            hist[name].append([s, clean_number(x.get("rsz"), 3), clean_number(x.get("rsmom"), 3), x.get("rank")])
    return write_json(dd / "market" / "sectors.json", {"available": True, "latest": last_s, "signals_session": sig_s,
                                                       "rows": rows, "history": dict(sorted(hist.items()))})


def build_sector_snapshot(cfg: Config, session: dt.date, rows: list[dict], generated_at: str, origin: str, source: str) -> dict:
    recs = sorted(rows, key=lambda x: x["ticker"])
    return {"schema_version": 1, "meta": {"strategy_id": "_SECTORS", "session": session.isoformat(), "generated_at": generated_at,
                                          "origin": origin, "source_file": Path(source).name, "record_count": len(recs),
                                          "content_hash": sha256_text(dumps(recs)), "revision": 1},
            "records": recs}


def parse_sector_export(cfg: Config, path: str | Path) -> dict[dt.date, list[dict]]:
    """CSV cua Hub_Sectors.afl -> {phien: [dong nganh]}."""
    from .csvio import parse_num, read_table
    from .util import parse_date
    t = read_table(path)
    need = ["Ticker", "DateNum", "RSZ", "RSMom"]
    idx = {c: t.col_index(c) for c in need + ["Close", "Ret5Pct", "Ret20Pct", "Ret60Pct", "ExcessVNI63Pct"]}
    if any(idx[c] is None for c in need):
        raise ValueError(f"File nganh thieu cot {need}: {t.header}")
    names = {}
    for k, v in cfg.sector_names.items():
        names["NGANH_" + k.upper().replace(" ", "")] = v
    out: dict[dt.date, list[dict]] = defaultdict(list)
    for row in t.rows:
        tk = row[idx["Ticker"]].strip().upper()
        d = parse_date(row[idx["DateNum"]])
        if not tk.startswith("NGANH_") or d is None:
            continue
        g = lambda c: clean_number(parse_num(row[idx[c]], t.decimal), 3) if idx[c] is not None else None  # noqa: E731
        out[d].append({"ticker": tk, "sector": names.get(tk, tk[6:].title()), "close": g("Close"), "rsz": g("RSZ"),
                       "rsmom": g("RSMom"), "ret5": g("Ret5Pct"), "ret20": g("Ret20Pct"), "ret60": g("Ret60Pct"),
                       "excess63": g("ExcessVNI63Pct")})
    return dict(out)

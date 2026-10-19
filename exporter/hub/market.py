"""Du lieu thi truong (EOD) dung de lam giau ket qua Exploration, do rong thi truong va hieu suat sau tin hieu.

Nguon: chinh cac file CSV EOD ma AmiBroker nap (import\\HOSE.csv, HNX.csv, UPCOM.csv, INDEX.csv).
Moi phep tinh dung LICH PHIEN GIAO DICH (ngay co VNINDEX), khong dung ngay lich.
Gia tri thieu giu la NaN/None, khong ep thanh 0 (ngoai tru GTGD phien khong giao dich = 0 dong, la su that).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from .config import Config


class MarketData:
    def __init__(self, open_: pd.DataFrame, close: pd.DataFrame, volume: pd.DataFrame,
                 bench_open: pd.Series, bench_close: pd.Series, exchange: dict[str, str],
                 names: dict[str, str] | None = None, sectors: dict[str, str] | None = None):
        cal = bench_close.dropna().index
        self.calendar: pd.DatetimeIndex = pd.DatetimeIndex(cal).sort_values()
        self.open = open_.reindex(self.calendar)
        self.close = close.reindex(self.calendar)
        self.volume = volume.reindex(self.calendar)
        self.bench_open = bench_open.reindex(self.calendar)
        self.bench_close = bench_close.reindex(self.calendar)
        self.exchange = exchange
        self.names = names or {}
        self.sectors = sectors or {}
        self._pos = {d: i for i, d in enumerate(self.calendar)}
        self._build()

    # ------------------------------------------------------------------ nap tu file
    @classmethod
    def load(cls, cfg: Config, end: dt.date | None = None) -> "MarketData":
        md = cfg.settings["market_data"]
        root = Path(md["import_dir"])
        bench = md.get("benchmark", "VNINDEX")
        idx = pd.read_csv(root / md["index_file"], usecols=["Ticker", "Date", "Open", "Close"])
        idx = idx[idx["Ticker"] == bench].copy()
        idx["Date"] = pd.to_datetime(idx["Date"])
        if end is not None:
            idx = idx[idx["Date"] <= pd.Timestamp(end)]
        idx = idx.drop_duplicates("Date", keep="last").set_index("Date").sort_index()
        lookback = int(md.get("lookback_sessions", 600))
        idx = idx.iloc[-lookback:]
        start = idx.index[0]
        frames = []
        exchange: dict[str, str] = {}
        for fn in md["stock_files"]:
            exch = Path(fn).stem.upper()
            df = pd.read_csv(root / fn, usecols=["Ticker", "Date", "Open", "Close", "Volume"],
                             dtype={"Ticker": str})
            df["Date"] = pd.to_datetime(df["Date"])
            df = df[(df["Date"] >= start) & (df["Date"] <= idx.index[-1])]
            for t in df["Ticker"].unique():
                exchange[t] = "UPCoM" if exch == "UPCOM" else exch
            frames.append(df)
        allp = pd.concat(frames, ignore_index=True).drop_duplicates(["Ticker", "Date"], keep="last")
        o = allp.pivot(index="Date", columns="Ticker", values="Open")
        c = allp.pivot(index="Date", columns="Ticker", values="Close")
        v = allp.pivot(index="Date", columns="Ticker", values="Volume")
        names = {}
        sp = root / md.get("symbols_file", "symbols.csv")
        if sp.exists():
            s = pd.read_csv(sp, dtype=str)
            names = dict(zip(s["Ticker"], s["Name"].fillna("")))
        sectors = {}
        smap = md.get("sector_map")
        if smap and Path(smap).exists():
            s = pd.read_csv(smap, dtype=str)
            col = "Nhom" if "Nhom" in s.columns else s.columns[1]
            for t, g in zip(s["Ticker"], s[col]):
                sectors.setdefault(t, cfg.sector_vi(g))
        return cls(o, c, v, idx["Open"], idx["Close"], exchange, names, sectors)

    # ------------------------------------------------------------------ chi bao
    def _build(self) -> None:
        c = self.close
        self.traded = c.notna()
        self.cf = c.ffill(limit=10)
        self.hist = self.traded.cumsum()
        val = (c * self.volume / 1e6).where(self.traded, 0.0)  # ty dong (gia nghin dong x KL / 1e6)
        self.adv20 = val.rolling(20, min_periods=20).mean().where(self.hist >= 20)
        self.ret = {n: (self.cf / self.cf.shift(n) - 1).where(self.traded & (self.hist > n)) for n in (1, 5, 20, 63)}
        self.rs = (self.ret[63].rank(axis=1, pct=True) * 100)
        self.ma = {n: self.cf.rolling(n, min_periods=n).mean() for n in (20, 50, 200)}
        self.hi250 = self.cf.rolling(250, min_periods=120).max()
        self.bench_ret = {n: self.bench_close / self.bench_close.shift(n) - 1 for n in (1, 5, 20, 63)}

    def sessions(self) -> list[dt.date]:
        return [d.date() for d in self.calendar]

    def last_session(self) -> dt.date:
        return self.calendar[-1].date()

    def has_session(self, d: dt.date) -> bool:
        return pd.Timestamp(d) in self._pos

    def prev_session(self, d: dt.date) -> dt.date | None:
        i = self._pos.get(pd.Timestamp(d))
        if i is None or i == 0:
            return None
        return self.calendar[i - 1].date()

    def session_gap(self, a: dt.date, b: dt.date) -> int | None:
        """So phien giao dich tu a den b (b sau a)."""
        ia, ib = self._pos.get(pd.Timestamp(a)), self._pos.get(pd.Timestamp(b))
        if ia is None or ib is None:
            return None
        return ib - ia

    def _val(self, frame: pd.DataFrame, ticker: str, ts: pd.Timestamp) -> float | None:
        if ticker not in frame.columns:
            return None
        x = frame.at[ts, ticker]
        return None if pd.isna(x) else float(x)

    def enrich(self, ticker: str, d: dt.date) -> dict:
        """Cac chi so chung cua 1 ma tai 1 phien (chi dung du lieu den het phien do)."""
        ts = pd.Timestamp(d)
        out = {"close": None, "ret_1d": None, "ret_5d": None, "ret_20d": None, "avg_trading_value_20": None,
               "relative_strength_score": None, "exchange": self.exchange.get(ticker), "name": self.names.get(ticker) or None,
               "sector": self.sectors.get(ticker)}
        if ts not in self._pos or ticker not in self.close.columns:
            return out
        out["close"] = self._val(self.close, ticker, ts)
        for n, k in ((1, "ret_1d"), (5, "ret_5d"), (20, "ret_20d")):
            r = self._val(self.ret[n], ticker, ts)
            out[k] = None if r is None else r * 100
        out["avg_trading_value_20"] = self._val(self.adv20, ticker, ts)
        out["relative_strength_score"] = self._val(self.rs, ticker, ts)
        return out

    # ------------------------------------------------------------------ do rong thi truong
    def breadth(self, dates: list[dt.date] | None = None) -> list[dict]:
        idx = self.calendar if dates is None else pd.DatetimeIndex([pd.Timestamp(d) for d in dates if pd.Timestamp(d) in self._pos])
        groups = {"ALL": list(self.close.columns)}
        for ex in ("HOSE", "HNX", "UPCoM"):
            groups[ex] = [t for t in self.close.columns if self.exchange.get(t) == ex]
        out = []
        for ts in idx:
            row = {"date": ts.date().isoformat()}
            for g, cols in groups.items():
                tr = self.traded.loc[ts, cols]
                cf = self.cf.loc[ts, cols]
                rec = {"n": int(tr.sum())}
                for n in (20, 50, 200):
                    ma = self.ma[n].loc[ts, cols]
                    ok = tr & ma.notna()
                    den = int(ok.sum())
                    rec[f"above_ma{n}"] = None if den == 0 else round(100.0 * float((cf[ok] > ma[ok]).sum()) / den, 2)
                    rec[f"n_ma{n}"] = den
                r1 = self.ret[1].loc[ts, cols]
                rec["advancers"] = int((r1 > 0).sum())
                rec["decliners"] = int((r1 < 0).sum())
                hi = self.hi250.loc[ts, cols]
                ok = tr & hi.notna()
                rec["new_high_52w"] = int((cf[ok] >= hi[ok]).sum())
                row[g] = rec
            out.append(row)
        return out

    # ------------------------------------------------------------------ hieu suat sau tin hieu
    def forward(self, ticker: str, d: dt.date, h: int, cost_pct: float) -> dict | None:
        """Vao lenh = gia MO CUA phien ke tiep sau ngay tin hieu (khong dung thong tin tuong lai);
        thoat = gia DONG CUA phien thu h tinh tu phien vao. Cua so chua du -> None."""
        i = self._pos.get(pd.Timestamp(d))
        if i is None or ticker not in self.close.columns:
            return None
        e = i + 1
        x = e + h - 1
        if x >= len(self.calendar):
            return None
        po = self.open[ticker].iloc[e]
        pc = self.cf[ticker].iloc[x]
        bo, bc = self.bench_open.iloc[e], self.bench_close.iloc[x]
        if pd.isna(po) or po <= 0 or pd.isna(pc) or pd.isna(bo) or pd.isna(bc) or bo <= 0:
            return None
        gross = (pc / po - 1) * 100
        bench = (bc / bo - 1) * 100
        return {"gross": round(float(gross), 3), "net": round(float(gross - cost_pct), 3),
                "bench": round(float(bench), 3), "excess": round(float(gross - bench), 3),
                "entry_date": self.calendar[e].date().isoformat(), "exit_date": self.calendar[x].date().isoformat()}

    def benchmark_returns(self, d: dt.date) -> dict:
        ts = pd.Timestamp(d)
        if ts not in self._pos:
            return {}
        out = {"close": float(self.bench_close.at[ts])}
        for n in (1, 5, 20, 63):
            r = self.bench_ret[n].at[ts]
            out[f"ret_{n}d"] = None if pd.isna(r) else round(float(r) * 100, 3)
        return out


def frames_from_records(records: list[dict]) -> MarketData:
    """Dung cho kiem thu: records = [{ticker, date, open, close, volume, exchange}], ma 'VNINDEX' la benchmark."""
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    b = df[df["ticker"] == "VNINDEX"].set_index("date").sort_index()
    s = df[df["ticker"] != "VNINDEX"]
    o = s.pivot(index="date", columns="ticker", values="open")
    c = s.pivot(index="date", columns="ticker", values="close")
    v = s.pivot(index="date", columns="ticker", values="volume")
    ex = {t: e for t, e in zip(s["ticker"], s.get("exchange", pd.Series(["HOSE"] * len(s))))}
    return MarketData(o, c, v, b["open"], b["close"], ex)

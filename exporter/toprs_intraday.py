"""Canh bao Top RS TRONG PHIEN qua Telegram (chay boi D:\\AmiBroker_VN\\scripts\\dnse_live.py moi 15 phut).

    python exporter\\toprs_intraday.py            # uoc tinh + gui (neu co ma moi)
    python exporter\\toprs_intraday.py --dry-run  # chi in ra, khong gui

Uoc tinh RS Rating hom nay = chuoi gia AmiBroker da chot (den phien truoc) + gia tam hom nay tu import\\LIVE_*.csv.
Bao: ma CHUA trong top co RS uoc tinh >= nguong vao; ma DANG trong top co RS uoc tinh < nguong roi.
Moi ma / loai toi da 1 tin / ngay. Ket qua chinh thuc chot trong tin cuoi ngay.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from hub import setup_logging  # noqa: E402
from hub.config import load_config  # noqa: E402
from hub.market import MarketData  # noqa: E402
from hub.notify import Telegram, intraday_alerts  # noqa: E402
from hub.toprs import intraday_estimate, load_icb  # noqa: E402
from hub.util import now_vn, read_json  # noqa: E402

log = logging.getLogger("hub")


def read_live(import_dir: Path, day: dt.date) -> tuple[dict[str, float], float | None, str | None]:
    live, bench = {}, None
    for mk in ("HOSE", "HNX", "UPCOM", "INDEX"):
        p = import_dir / f"LIVE_{mk}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype={"Ticker": str})
        df = df[df["Date"] == day.isoformat()]
        for t, c in zip(df["Ticker"], df["Close"]):
            if t == "VNINDEX":
                bench = float(c)
            elif mk != "INDEX":
                live[t] = float(c)
    mt = None
    p = import_dir / "LIVE_INDEX.csv"
    if p.exists():
        mt = dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%H:%M")
    return live, bench, mt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    setup_logging(cfg)
    tg = Telegram(cfg)
    if not a.dry_run and (not tg.configured or not tg.flags.get("intraday", True)):
        log.info("Canh bao trong phien: Telegram chua cau hinh / dang tat -> bo qua")
        return 0
    now = now_vn()
    doc = read_json(cfg.data_dir / "toprs" / "latest.json")
    if not doc or not doc.get("available"):
        log.info("Canh bao trong phien: chua co data/toprs/latest.json")
        return 0
    market = MarketData.load_best(cfg)
    if market.last_session().isoformat() != doc["session"] or market.last_session() >= now.date():
        log.info("Canh bao trong phien: chuoi gia (%s) / Top RS (%s) khong khop hoac da co phien hom nay -> bo qua",
                 market.last_session(), doc["session"])
        return 0
    # du lieu chot phai la phien lien truoc hom nay (thu 2-6); cu hon -> uoc tinh se lech phien -> khong bao
    prev = now.date() - dt.timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= dt.timedelta(days=1)
    if market.last_session() < prev:
        log.info("Canh bao trong phien: du lieu chot moi den %s (can %s, co the nghi le / CapNhat chua chay) -> bo qua",
                 market.last_session(), prev)
        return 0
    live, bench, mt = read_live(Path(cfg.settings.get("notify", {}).get("import_dir_live", r"D:\AmiBroker_VN\import")), now.date())
    if bench is None or not live:
        log.info("Canh bao trong phien: chua co gia tam hom nay")
        return 0
    est = intraday_estimate(market, doc, live, bench, load_icb(cfg))
    asof = f"{mt or now.strftime('%H:%M')} {now:%d/%m} · giá tạm {est['coverage']}/{est['universe']} mã"
    log.info("Top RS trong phien: %d sap vao, %d co the roi (gia tam %d/%d ma)", len(est["enters"]), len(est["exits"]),
             est["coverage"], est["universe"])
    text = intraday_alerts(cfg, est["enters"], est["exits"], asof, tg, dry_run=a.dry_run)
    if a.dry_run:
        print(text or "(khong co ma moi can bao)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

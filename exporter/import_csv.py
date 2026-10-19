"""NHAP TAY ket qua Exploration tu file CSV (khi chua cai dat ket noi COM).

Trong AmiBroker: chay Exploration -> chuot phai bang ket qua -> Export -> luu CSV, roi:

    python exporter\\import_csv.py --strategy VCP --file D:\\exports\\vcp.csv
    python exporter\\import_csv.py --strategy RS --file rs.csv --session 2026-10-16
    python exporter\\import_csv.py --strategy VCP --file vcp_range.csv --range   # file nhieu phien (Range From-To)

File phai co cac cot khai bao trong strategy_config.yaml (columns.*). Dung CHUNG bo kiem tra + chuan hoa
voi duong tu dong. Sau khi nhap, du lieu web duoc dung lai (data/), chay publish.py de day len GitHub.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub import setup_logging  # noqa: E402
from hub.config import load_config  # noqa: E402
from hub.derive import build_site  # noqa: E402
from hub.pipeline import RunRecorder, ingest_file  # noqa: E402
from hub.util import iso, now_vn  # noqa: E402

log = logging.getLogger("hub")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--session", help="YYYY-MM-DD; mac dinh = phien EOD moi nhat (hoac ngay lon nhat trong file)")
    ap.add_argument("--range", action="store_true", help="File chua nhieu phien -> luu moi phien thanh 1 snapshot")
    ap.add_argument("--allow-empty", action="store_true")
    ap.add_argument("--no-market", action="store_true", help="Khong lam giau bang du lieu gia (gia, GTGD, RS de trong)")
    ap.add_argument("--origin", default="manual", choices=["manual", "demo"])
    ap.add_argument("--data-dir", help="Thu muc data khac (mac dinh: <repo>/data)")
    a = ap.parse_args()

    cfg = load_config(data_dir=a.data_dir)
    setup_logging(cfg)
    s = cfg.strategy(a.strategy)
    src = Path(a.file)
    market = None
    if not a.no_market:
        from hub.market import MarketData
        try:
            market = MarketData.load(cfg)
        except (OSError, KeyError, ValueError) as e:
            log.warning("Khong nap duoc du lieu gia (%s) -> nhap khong lam giau", e)
    if a.session:
        session = dt.date.fromisoformat(a.session)
    elif market is not None:
        session = market.last_session()
    else:
        from hub.normalize import parse_export
        pe = parse_export(s, src, session=None) if s.columns.get("date") else None
        if not pe or not pe.by_date:
            log.error("Can --session (file khong co cot ngay va khong co du lieu gia)")
            return 2
        session = max(pe.by_date)
    arch = cfg.archive_dir / "raw" / session.isoformat()
    arch.mkdir(parents=True, exist_ok=True)
    kept = arch / f"{s.id}_{a.origin}_{now_vn():%H%M%S}{src.suffix or '.csv'}"
    shutil.copy2(src, kept)  # luu ban goc de doi chieu
    rr = RunRecorder(cfg, a.origin)
    rr.rec["session"] = session.isoformat()
    rng = None
    if a.range:
        from hub.normalize import parse_export
        pe = parse_export(s, kept, session=session)
        if not pe.by_date:
            log.error("File khong co dong hop le nao")
            rr.finish("failed", "File khong co dong hop le")
            return 2
        rng = (min(pe.by_date), max(pe.by_date))
    n = ingest_file(cfg, s, kept, market, session, origin=a.origin, rr=rr, allow_empty=a.allow_empty, backfill=rng)
    if n == 0:
        rr.finish("failed", rr.rec["steps"][-1].get("message") if rr.rec["steps"] else "Khong luu duoc")
        log.error("Nhap that bai: %s", rr.rec["message"])
        return 2
    info = build_site(cfg, market, build_time=iso(now_vn()), demo=a.origin == "demo")
    rr.step("build", "ok", message=f"{info['sessions']} phien, {info['files_changed']} file thay doi")
    rr.finish("success", f"Nhap {s.id} phien {session}: {n} snapshot")
    log.info("Xong: %s", rr.rec["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

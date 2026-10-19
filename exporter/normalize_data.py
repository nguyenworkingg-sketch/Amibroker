"""Dung lai TOAN BO du lieu web (data/sessions, history, tickers, market, performance, meta) tu cac snapshot.

    python exporter\\normalize_data.py              # co du lieu gia EOD (hieu suat sau tin hieu, do rong thi truong)
    python exporter\\normalize_data.py --no-market  # chi tu snapshot

Tat dinh: cung snapshot + cung du lieu gia -> cung file JSON (file khong doi se khong bi ghi lai).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub import setup_logging  # noqa: E402
from hub.config import load_config  # noqa: E402
from hub.derive import build_site  # noqa: E402
from hub.util import iso, now_vn, read_json  # noqa: E402

log = logging.getLogger("hub")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-market", action="store_true")
    ap.add_argument("--data-dir")
    ap.add_argument("--demo", action="store_true", help="Danh dau du lieu la mo phong")
    a = ap.parse_args()
    cfg = load_config(data_dir=a.data_dir)
    setup_logging(cfg)
    market = None
    if not a.no_market:
        from hub.market import MarketData
        market = MarketData.load(cfg)
    meta = read_json(cfg.data_dir / "meta.json", {})
    demo = a.demo or bool(meta.get("demo"))
    info = build_site(cfg, market, build_time=iso(now_vn()), demo=demo)
    log.info("Dung lai: %d phien, %d file thay doi", info["sessions"], info["files_changed"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

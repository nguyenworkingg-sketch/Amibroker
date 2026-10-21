"""Chay cac Exploration da bat trong AmiBroker -> kiem tra -> chuan hoa -> JSON -> (tuy chon) day len GitHub.

Vi du:
    python exporter\\run_explorations.py                      # phien EOD moi nhat, tat ca chien luoc dang bat
    python exporter\\run_explorations.py --publish            # ... va day len GitHub (lich 08:30 dung lenh nay)
    python exporter\\run_explorations.py --strategies VCP,RS  # chi mot so chien luoc
    python exporter\\run_explorations.py --backfill 120       # tai tao 120 phien gan nhat (chien luoc ho tro)

Ma thoat: 0 = thanh cong/khong co gi moi, 1 = loi mot phan, 2 = that bai, 3 = hoan (dang ban).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub import setup_logging  # noqa: E402
from hub.config import load_config  # noqa: E402
from hub.market import MarketData  # noqa: E402
from hub.pipeline import conflicting_processes, run_amibroker  # noqa: E402

log = logging.getLogger("hub")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategies", help="Danh sach ID, cach nhau dau phay (mac dinh: tat ca dang bat)")
    ap.add_argument("--backfill", type=int, metavar="N", help="Tai tao N phien gan nhat (chi chien luoc supports_backfill)")
    ap.add_argument("--allow-empty", action="store_true", help="Chap nhan ket qua 0 ma du phien truoc co nhieu ma")
    ap.add_argument("--publish", action="store_true", help="Commit + push thu muc data/ len GitHub khi thanh cong")
    ap.add_argument("--wait-minutes", type=int, default=0, help="Neu AmiBroker dang ban, cho toi da N phut roi thu lai")
    ap.add_argument("--no-sectors", action="store_true")
    ap.add_argument("--catchup", action="store_true",
                    help="Chay bu: chi chay neu phien EOD moi nhat chua co tren web; chap nhan AmiBroker dang co nen trong phien")
    a = ap.parse_args()

    cfg = load_config()
    setup_logging(cfg)
    deadline = time.time() + 60 * a.wait_minutes
    while a.wait_minutes and conflicting_processes(cfg) and time.time() < deadline:
        log.info("Dang co tien trinh dung AmiBroker (%s) -> cho 1 phut", ", ".join(conflicting_processes(cfg)))
        time.sleep(60)

    log.info("Nap du lieu EOD ...")
    market = MarketData.load(cfg)
    if a.catchup:
        from hub.util import read_json
        meta = read_json(cfg.data_dir / "meta.json", {})
        done = {s["id"]: s.get("last_session") for s in meta.get("strategies", [])}
        sess = market.last_session().isoformat()
        missing = [s.id for s in cfg.enabled() if s.supports_backfill and (done.get(s.id) or "") < sess]
        if not missing:
            log.info("Chay bu: phien %s da co tren web -> khong can chay", sess)
            return 0
        log.info("Chay bu phien %s cho: %s", sess, ", ".join(missing))
    log.info("Lich phien: %d phien, phien cuoi %s, %d ma", len(market.calendar), market.last_session(), market.close.shape[1])
    ids = [x.strip().upper() for x in a.strategies.split(",")] if a.strategies else None
    rng = None
    if a.backfill:
        ss = market.sessions()
        rng = (ss[-min(a.backfill, len(ss))], ss[-1])
        log.info("Tai tao lich su %s .. %s", *rng)
    rec = run_amibroker(cfg, market, strategy_ids=ids, backfill=rng, allow_empty=a.allow_empty, with_sectors=not a.no_sectors,
                        catchup=a.catchup)
    log.info("KET QUA: %s - %s", rec["result"], rec["message"])
    for s in rec["steps"]:
        log.info("  %-10s %-16s %s", s["name"], s["status"], s.get("message") or "")
    code = {"success": 0, "partial": 1, "failed": 2, "skipped": 3}.get(rec["result"], 2)
    if a.publish and rec["result"] in ("success", "partial"):
        from publish import publish
        try:
            r = publish(cfg)
            log.info("PUBLISH: %s", r["message"])
            if not r.get("published") and "Khong co" not in r["message"]:
                code = max(code, 1)
        except RuntimeError as e:
            log.error("PUBLISH loi: %s", e)
            code = max(code, 1)
    # Tin Telegram cuoi ngay (Top RS) - chi khi chay that (khong phai tai tao lich su), moi phien 1 lan
    if not a.backfill and rec["result"] in ("success", "partial"):
        try:
            from hub.notify import Telegram, eod_toprs
            from hub.util import read_json
            tg = Telegram(cfg)
            if tg.configured:
                sent = eod_toprs(cfg, read_json(cfg.data_dir / "toprs" / "latest.json"), tg)
                log.info("TELEGRAM cuoi ngay: %s", "da gui" if sent else "khong gui (da gui phien nay / loi)")
        except Exception as e:  # thong bao loi khong lam hong lan chay
            log.error("TELEGRAM loi: %s", e)
    return code


if __name__ == "__main__":
    sys.exit(main())

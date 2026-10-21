"""Tien ich kiem thu: cau hinh tro vao thu muc tam, du lieu gia tong hop."""
from __future__ import annotations

import datetime as dt
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "exporter"))

from hub.config import load_config  # noqa: E402
from hub.market import frames_from_records  # noqa: E402


def temp_config():
    d = Path(tempfile.mkdtemp(prefix="hubtest_"))
    cfg = load_config(data_dir=d / "data", archive_dir=d / "archive")
    # KHONG BAO GIO ghi / doc file that tren may khi kiem thu (20/10/2026: test da ghi de danh sach ro Top RS)
    cfg.settings.setdefault("top_rs", {})["live_watchlist_file"] = str(d / "live_watchlist_toprs.txt")
    cfg.settings.setdefault("notify", {})["telegram_config"] = str(d / "telegram_khong_co.ini")
    cfg.settings["notify"]["import_dir_live"] = str(d / "import")
    return cfg, d


def weekdays(start: dt.date, n: int) -> list[dt.date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def synthetic_market(n: int = 120, tickers=("AAA", "BBB", "CCC"), start=dt.date(2026, 1, 5)):
    """Gia tang deu theo ma: AAA +1%/phien, BBB 0, CCC -0.5%; VNINDEX +0.2%. Mo cua = dong cua phien truoc."""
    days = weekdays(start, n)
    drift = {"AAA": 0.01, "BBB": 0.0, "CCC": -0.005}
    recs = []
    for t in list(tickers) + ["VNINDEX"]:
        p = 1000.0 if t == "VNINDEX" else 20.0
        g = 0.002 if t == "VNINDEX" else drift.get(t, 0.0)
        prev = p
        for d in days:
            p = prev * (1 + g)
            recs.append({"ticker": t, "date": d.isoformat(), "open": prev, "close": p, "volume": 1_000_000, "exchange": "HOSE"})
            prev = p
    m = frames_from_records(recs)
    m.MIN_SESSIONS = 0  # du lieu tong hop ngan, khong ap dung nguong lich su toi thieu
    return m, days


def write(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(encoding))
    return path

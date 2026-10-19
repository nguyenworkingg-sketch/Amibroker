"""AmiBroker Exploration Hub - exporter/processor."""
import logging
import sys

from .util import now_vn

__version__ = "1.0.0"


def setup_logging(cfg) -> None:
    d = cfg.archive_dir / "logs"
    d.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger("hub")
    root.setLevel(logging.INFO)
    if root.handlers:
        return
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")  # cua so cmd/Task Scheduler dung cp1252
        except (AttributeError, ValueError):
            pass
    fh = logging.FileHandler(d / f"hub_{now_vn():%Y%m%d}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)

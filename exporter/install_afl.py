"""Cai cac file adapter Hub_*.afl vao thu muc Formulas\\Hub cua AmiBroker (theo strategy_config.yaml).

    python exporter\\install_afl.py
Chi chep file Hub_*.afl; khong sua bat ky file AFL goc nao.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub.config import REPO_ROOT, load_config  # noqa: E402


def main() -> int:
    cfg = load_config()
    dst = Path(cfg.settings["amibroker"]["formulas_dir"])
    dst.mkdir(parents=True, exist_ok=True)
    src = REPO_ROOT / "amibroker" / "afl"
    n = 0
    for f in sorted(src.glob("Hub_*.afl")):
        shutil.copy2(f, dst / f.name)
        print(f"  {f.name} -> {dst}")
        n += 1
    print(f"Da cai {n} file AFL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

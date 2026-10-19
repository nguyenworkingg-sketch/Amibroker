"""Dang du lieu len GitHub: chi commit cac duong dan duoc phep (mac dinh: data/), khong force-push.

    python exporter\\publish.py            # commit + push neu co thay doi
    python exporter\\publish.py --dry-run  # chi liet ke file se commit

Xac thuc: dung Git Credential Manager / GitHub CLI da dang nhap tren may (khong luu token trong repo).
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hub import setup_logging  # noqa: E402
from hub.config import REPO_ROOT, load_config  # noqa: E402
from hub.util import iso, now_vn, read_json, write_json  # noqa: E402

log = logging.getLogger("hub")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} that bai: {(p.stderr or p.stdout).strip()}")
    return p


def publish(cfg, dry_run: bool = False, message: str | None = None) -> dict:
    pub = cfg.settings.get("publish", {})
    allowed = pub.get("allowed_paths", ["data"])
    remote, branch = pub.get("remote", "origin"), pub.get("branch", "main")
    changed = git("status", "--porcelain", "--", *allowed).stdout.strip().splitlines()
    others = [ln for ln in git("status", "--porcelain").stdout.strip().splitlines() if ln and ln not in changed]
    if others:
        log.info("Bo qua %d thay doi ngoai %s (khong tu dong commit)", len(others), allowed)
    if not changed:
        ahead = git("rev-list", "--count", f"{remote}/{branch}..HEAD", check=False).stdout.strip()
        if ahead in ("", "0"):
            return {"published": False, "message": "Khong co du lieu moi"}
    if dry_run:
        return {"published": False, "message": f"{len(changed)} file se duoc commit", "files": changed[:50]}
    st_path = cfg.data_dir / "status.json"
    st = read_json(st_path, {})
    t = iso(now_vn())
    if changed:
        st["last_publication"] = {"at": t, "session": (st.get("last_success") or {}).get("session")}
        write_json(st_path, st, compact=False)
        git("add", "--", *allowed)
        sess = (st.get("last_success") or {}).get("session") or "?"
        git("commit", "-m", message or f"Dữ liệu Exploration phiên {sess}", "--", *allowed)
    git("pull", "--rebase", "--autostash", remote, branch)
    p = git("push", remote, f"HEAD:{branch}", check=False)
    if p.returncode != 0:
        return {"published": False, "message": "Push that bai (du lieu da commit tai may, lan sau se day lai): "
                + (p.stderr or p.stdout).strip()[-400:]}
    return {"published": True, "message": f"Da day len {remote}/{branch} luc {t}", "at": t}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-m", "--message")
    a = ap.parse_args()
    cfg = load_config()
    setup_logging(cfg)
    try:
        r = publish(cfg, a.dry_run, a.message)
    except RuntimeError as e:
        log.error("%s", e)
        return 2
    log.info("%s", r["message"])
    return 0 if r.get("published") or "Khong co" in r["message"] or a.dry_run else 1


if __name__ == "__main__":
    sys.exit(main())

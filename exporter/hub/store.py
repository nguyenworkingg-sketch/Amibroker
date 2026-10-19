"""Luu snapshot theo phien: nguyen tu, chong trung, khong de du lieu rong/loi thay du lieu hop le."""
from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from .config import Config
from .util import read_json, write_json


class EmptySuspicious(Exception):
    """Ket qua rong trong khi phien truoc co nhieu ma -> nghi loi, khong ghi."""


def snapshot_path(cfg: Config, session: dt.date | str, sid: str) -> Path:
    s = session if isinstance(session, str) else session.isoformat()
    return cfg.data_dir / "snapshots" / s / f"{sid}.json"


def list_snapshots(cfg: Config, sid: str | None = None) -> list[tuple[str, str, Path]]:
    """[(session, strategy_id, path)] sap theo phien tang dan."""
    root = cfg.data_dir / "snapshots"
    out = []
    if not root.exists():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in sorted(d.glob("*.json")):
            if sid is None or f.stem == sid:
                out.append((d.name, f.stem, f))
    return out


def previous_snapshot(cfg: Config, sid: str, session: str) -> dict | None:
    prev = [p for s, _, p in list_snapshots(cfg, sid) if s < session]
    return read_json(prev[-1]) if prev else None


def save_snapshot(cfg: Config, snap: dict, *, allow_empty: bool = False, force: bool = False) -> str:
    """Tra ve 'created' | 'unchanged' | 'replaced'."""
    meta = snap["meta"]
    sid, session = meta["strategy_id"], meta["session"]
    path = snapshot_path(cfg, session, sid)
    old = read_json(path) if path.exists() else None
    if meta["record_count"] == 0 and not allow_empty:
        guard = int(cfg.settings.get("empty_guard_min_previous", 5))
        ref = old or previous_snapshot(cfg, sid, session)
        if ref and ref["meta"]["record_count"] >= guard:
            raise EmptySuspicious(f"{sid} {session}: 0 ma dat, trong khi lan truoc co {ref['meta']['record_count']} ma "
                                  f"-> nghi loi, giu nguyen du lieu cu (dung --allow-empty neu dung la 0)")
    if old is not None:
        if old["meta"].get("content_hash") == meta["content_hash"] and not force:
            return "unchanged"
        if old["meta"]["origin"] in ("live", "manual") and meta["origin"] == "backfill" and not force:
            # khong de ban tai tao lich su ghi de ket qua chay that
            return "unchanged"
        bak = cfg.archive_dir / "replaced" / f"{session}_{sid}_{old['meta']['content_hash'][:10]}.json"
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, bak)
        meta["revision"] = int(old["meta"].get("revision", 1)) + 1
        write_json(path, snap)
        return "replaced"
    write_json(path, snap)
    return "created"

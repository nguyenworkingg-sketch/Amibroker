"""Dieu phoi: khoa chong chay trung -> kiem tra xung dot -> chay Exploration -> kiem tra -> chuan hoa
-> luu snapshot -> dung du lieu web -> (tuy chon) publish. Ghi trang thai ro rang cho moi buoc."""
from __future__ import annotations

import contextlib
import datetime as dt
import logging
import os
import time
import uuid
from pathlib import Path

from . import amibroker
from .config import Config, Strategy
from .derive import build_sector_snapshot, build_site, parse_sector_export
from .normalize import ValidationError, build_snapshot, parse_export
from .store import EmptySuspicious, save_snapshot
from .util import iso, now_vn, read_json, sha256_file, write_json

log = logging.getLogger("hub")


class HubError(Exception):
    pass


class Busy(HubError):
    """Dang co tien trinh khac dung AmiBroker / exporter khac dang chay -> hoan, khong phai loi du lieu."""


# ---------------------------------------------------------------------- khoa + xung dot
@contextlib.contextmanager
def run_lock(cfg: Config):
    lock = cfg.archive_dir / "hub.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        try:
            pid = int(lock.read_text().split()[0])
        except (ValueError, IndexError, OSError):
            pid = -1
        if pid > 0 and _pid_alive(pid):
            raise Busy(f"Exporter khac dang chay (pid {pid}); khoa: {lock}")
        log.warning("Xoa khoa cu cua tien trinh da ket thuc (pid %s)", pid)
        lock.unlink()
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w") as f:
        f.write(f"{os.getpid()} {iso(now_vn())}\n")
    try:
        yield
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:  # pragma: no cover
        return True


def conflicting_processes(cfg: Config) -> list[str]:
    try:
        import psutil
    except ImportError:  # pragma: no cover
        return []
    keys = [k.lower() for k in cfg.settings.get("conflicting_processes", [])]
    # bo qua chinh minh va tien trinh cha (vd. TuDong_CapNhat.bat goi Hub sau khi CapNhat xong)
    mine = {os.getpid()} | {p.pid for p in psutil.Process().parents()}
    found = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            if p.info["pid"] in mine or not p.info["cmdline"]:
                continue
            cl = " ".join(p.info["cmdline"]).lower()
            for k in keys:
                if k in cl:
                    found.append(f"{k} (pid {p.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(set(found))


# ---------------------------------------------------------------------- trang thai
class RunRecorder:
    def __init__(self, cfg: Config, kind: str):
        self.cfg = cfg
        self.rec = {"run_id": uuid.uuid4().hex[:12], "kind": kind, "started_at": iso(now_vn()), "finished_at": None,
                    "session": None, "result": "running", "message": None, "steps": [], "published": False,
                    "published_at": None}

    def step(self, name: str, status: str, **kw) -> None:
        s = {"name": name, "status": status, **kw}
        self.rec["steps"].append(s)
        log.info("%s: %s %s", name, status, kw.get("message") or "")

    def finish(self, result: str, message: str | None = None) -> dict:
        self.rec["finished_at"] = iso(now_vn())
        self.rec["result"] = result
        self.rec["message"] = message
        path = self.cfg.data_dir / "status.json"
        st = read_json(path, {"runs": [], "strategies": {}})
        st["runs"] = ([self.rec] + st.get("runs", []))[:60]
        strat = st.setdefault("strategies", {})
        for s in self.rec["steps"]:
            sid = s.get("strategy")
            if not sid:
                continue
            e = strat.setdefault(sid, {})
            e["last_status"] = s["status"]
            e["last_run_at"] = self.rec["finished_at"]
            e["last_message"] = s.get("message")
            if s["status"] in ("created", "unchanged", "replaced"):
                e["last_success_session"] = s.get("session") or e.get("last_success_session")
                e["last_success_at"] = self.rec["finished_at"]
                e["last_records"] = s.get("records")
                e["last_error"] = None
            elif s["status"] in ("error", "invalid", "empty_suspicious", "timeout"):
                e["last_error"] = s.get("message")
        if result in ("success", "partial"):
            st["last_success"] = {"run_id": self.rec["run_id"], "at": self.rec["finished_at"], "session": self.rec["session"],
                                  "kind": self.rec["kind"]}
        st["last_run"] = {k: self.rec[k] for k in ("run_id", "kind", "started_at", "finished_at", "session", "result", "message")}
        write_json(path, st, compact=False)
        return self.rec


# ---------------------------------------------------------------------- phien
def expected_session(cfg: Config, market) -> dt.date:
    s = market.last_session()
    now = now_vn()
    hh, mm = (int(x) for x in str(cfg.settings.get("session_close_time", "15:30")).split(":"))
    if s == now.date() and (now.hour, now.minute) < (hh, mm):
        raise HubError(f"Du lieu EOD co phien {s} nhung chua qua {hh:02d}:{mm:02d} -> phien chua hoan tat, khong xuat")
    if s > now.date():
        raise HubError(f"Ngay du lieu {s} o tuong lai?")
    return s


def verify_probe(pr: dict, session: dt.date, market, bench: str, sec_sym: str | None, backfill: bool) -> tuple[str | None, bool]:
    """Doi chieu nen cuoi trong AmiBroker voi so lieu EOD da chot. Tra ve (ghi chu, chi_so_nganh_ok).
    Loi -> HubError (khong xuat gi). Kiem tra CA ngay LAN gia dong cua: nen trong phien (DNSE) co cung ngay
    voi phien EOD nhung gia khac -> phai tu choi."""
    s = session.isoformat()
    b = (pr.get("bars") or {}).get(bench) or {"date": pr.get("last_bar")}
    note = None
    if backfill and (b.get("date") or "") > s:
        # tai tao chi lay phien <= phien EOD; adapter tinh nhan qua nen nen sau do khong anh huong
        note = f"AmiBroker co nen {b['date']} sau phien EOD {s}: chi tai tao den {s}"
    elif b.get("date") != s:
        why = "co nen trong phien chua chot" if (b.get("date") or "") > s else "chua nap du lieu moi"
        raise HubError(f"AmiBroker co nen cuoi {b.get('date')} khac phien EOD {s} ({why}) -> khong xuat de tranh gan nham ngay")
    else:
        eod = float(market.bench_close.iloc[-1]) if market is not None and market.last_session() == session else None
        c = b.get("close")
        if eod is not None and c is not None and abs(c / eod - 1) > 0.0005:
            raise HubError(f"{bench} phien {s} trong AmiBroker dong cua {c:.2f} khac so lieu chot {eod:.2f} -> AmiBroker con "
                           "nen trong phien (chua chay CapNhat / nap EOD that bai). Khong xuat.")
    sectors_ok = True
    if sec_sym:
        sb = (pr.get("bars") or {}).get(sec_sym)
        sectors_ok = bool(sb) and (sb.get("date") or "") >= s
    return note, sectors_ok


def _formula(cfg: Config, name: str) -> str:
    p = Path(cfg.settings["amibroker"]["formulas_dir"]) / name
    if not p.exists():
        raise HubError(f"Chua cai file AFL {p} (chay: python exporter\\install_afl.py)")
    return str(p)


def _job(cfg: Config, strat: Strategy | dict, out: Path, rng: tuple[dt.date, dt.date] | None) -> dict:
    g = (lambda k, d=None: getattr(strat, k, d)) if isinstance(strat, Strategy) else (lambda k, d=None: strat.get(k, d))
    apx = g("apx")
    job = {"kind": "explore", "database": cfg.settings["amibroker"]["database"], "out_csv": str(out),
           "afl": None if (apx and Path(apx).exists()) else _formula(cfg, g("afl")),
           "apx": apx if (apx and Path(apx).exists()) else None,
           "apply_to": g("apply_to", "all"), "two_pass": bool(g("two_pass", False))}
    if rng and g("supports_backfill", False):
        job.update({"range": "range", "from": rng[0].isoformat(), "to": rng[1].isoformat()})
    else:
        job["range"] = "all" if job["two_pass"] else "last"
    return job


def run_amibroker(cfg: Config, market, *, strategy_ids: list[str] | None = None, backfill: tuple[dt.date, dt.date] | None = None,
                  allow_empty: bool = False, with_sectors: bool = True, check_conflicts: bool = True) -> dict:
    kind = "backfill" if backfill else "daily"
    rr = RunRecorder(cfg, kind)
    try:
        with run_lock(cfg):
            if check_conflicts:
                busy = conflicting_processes(cfg)
                if busy:
                    raise Busy("Dang chay: " + ", ".join(busy) + " -> hoan de khong xung dot voi AmiBroker")
            session = expected_session(cfg, market)
            rr.rec["session"] = session.isoformat()
            ab = cfg.settings["amibroker"]
            raw_dir = cfg.archive_dir / "raw" / session.isoformat()
            raw_dir.mkdir(parents=True, exist_ok=True)
            bench = ab.get("benchmark_symbol", "VNINDEX")
            sec_sym = ab.get("sector_check_symbol")
            pr = amibroker.probe(ab["database"], bench, raw_dir, check_symbols=[sec_sym] if sec_sym else [])
            rr.step("probe", "ok", message=f"database {pr['database']}, nen cuoi {pr['last_bar']}")
            note, sectors_ok = verify_probe(pr, session, market, bench, sec_sym, bool(backfill))
            if note:
                rr.step("probe", "ok", message=note)
            strategies = [s for s in cfg.enabled() if not strategy_ids or s.id in strategy_ids]
            if backfill:
                strategies = [s for s in strategies if s.supports_backfill]
            timeout = int(ab.get("timeout_seconds", 1200))
            ok = fail = 0
            sector_dep = set(ab.get("sector_dependent", []))
            for s in [x for x in strategies if x.id in sector_dep and not sectors_ok]:
                rr.step(s.id, "error", strategy=s.id, session=session.isoformat(),
                        message=f"Chi so nganh {sec_sym} trong AmiBroker chua cap nhat den phien {session} -> bo qua")
                fail += 1
            strategies = [x for x in strategies if sectors_ok or x.id not in sector_dep]
            for s in strategies:
                stamp = now_vn().strftime("%H%M%S")
                out = raw_dir / f"{s.id}_{kind}_{stamp}.csv"
                rng = backfill if backfill else ((session, session) if s.supports_backfill else None)
                t0 = time.time()
                res = None
                for attempt in range(int(ab.get("retries", 1)) + 1):
                    try:
                        res = amibroker.run_job(_job(cfg, s, out, rng), timeout)
                        break
                    except amibroker.AmiBrokerError as e:
                        err = str(e)
                        log.warning("%s lan %d loi: %s", s.id, attempt + 1, err)
                        if "Qua thoi gian" in err:
                            break  # khong thu lai khi qua thoi gian (AmiBroker co the con ban)
                        time.sleep(3)
                if res is None:
                    rr.step(s.id, "error", strategy=s.id, session=session.isoformat(), message=err)
                    fail += 1
                    continue
                n = ingest_file(cfg, s, out, market, session, origin=kind if backfill else "live", rr=rr,
                                allow_empty=allow_empty or bool(backfill), backfill=backfill, seconds=round(time.time() - t0, 1))
                ok += n > 0
                fail += n == 0
            if with_sectors and cfg.auxiliary and not sectors_ok:
                rr.step("_SECTORS", "error", message=f"Chi so nganh {sec_sym} chua cap nhat den phien {session} -> bo qua")
            elif with_sectors and cfg.auxiliary:
                aux = cfg.auxiliary[0]
                out = raw_dir / f"_SECTORS_{kind}_{now_vn().strftime('%H%M%S')}.csv"
                try:
                    amibroker.run_job(_job(cfg, aux, out, backfill or (session, session)), timeout)
                    n = ingest_sectors(cfg, out, kind if backfill else "live")
                    rr.step("_SECTORS", "ok", message=f"{n} phien nganh")
                except Exception as e:  # nganh la phu tro, khong lam hong ca lan chay
                    rr.step("_SECTORS", "error", message=str(e))
            info = build_site(cfg, market, build_time=iso(now_vn()))
            rr.step("build", "ok", message=f"{info['sessions']} phien, {info['files_changed']} file thay doi")
            result = "success" if fail == 0 else ("partial" if ok else "failed")
            return rr.finish(result, f"{ok} chien luoc ok, {fail} loi")
    except Busy as e:
        return rr.finish("skipped", str(e))
    except (HubError, amibroker.AmiBrokerError) as e:
        log.error("%s", e)
        return rr.finish("failed", str(e))


def ingest_file(cfg: Config, s: Strategy, path: Path, market, session: dt.date, *, origin: str, rr: RunRecorder | None,
                allow_empty: bool = False, backfill: tuple[dt.date, dt.date] | None = None, seconds: float | None = None,
                generated_at: str | None = None) -> int:
    """Kiem tra + chuan hoa + luu. Tra ve so snapshot luu thanh cong (0 neu loi)."""
    gen = generated_at or iso(now_vn())
    try:
        pe = parse_export(s, path, session=session, only_session=not backfill and bool(s.columns.get("date")))
    except ValidationError as e:
        if rr:
            rr.step(s.id, "invalid", strategy=s.id, session=session.isoformat(), message=str(e))
        return 0
    sha = sha256_file(path)
    if backfill:
        if pe.rows_total == 0:
            if rr:
                rr.step(s.id, "invalid", strategy=s.id, message="File tai tao lich su khong co dong nao")
            return 0
        dates = [d for d in market.sessions() if backfill[0] <= d <= backfill[1]] if market else sorted(pe.by_date)
    else:
        dates = [session]
    saved = 0
    statuses = {}
    for d in dates:
        snap = build_snapshot(s, d, pe.by_date.get(d, []), market, origin=origin, source_file=str(path), source_sha256=sha,
                              generated_at=gen, data_asof=session.isoformat() if not backfill else d.isoformat(),
                              warnings=pe.warnings)
        try:
            r = save_snapshot(cfg, snap, allow_empty=allow_empty)
        except EmptySuspicious as e:
            if rr:
                rr.step(s.id, "empty_suspicious", strategy=s.id, session=d.isoformat(), message=str(e))
            continue
        statuses[r] = statuses.get(r, 0) + 1
        saved += 1
    if rr and saved:
        main = "created" if statuses.get("created") else ("replaced" if statuses.get("replaced") else "unchanged")
        msg = ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items()))
        n_last = len(pe.by_date.get(session, [])) if not backfill else pe.rows_passing
        rr.step(s.id, main, strategy=s.id, session=session.isoformat() if not backfill else f"{dates[0]}..{dates[-1]}",
                records=n_last, seconds=seconds, message=msg + (f"; canh bao: {'; '.join(pe.warnings)}" if pe.warnings else ""))
    return saved


def ingest_sectors(cfg: Config, path: Path, origin: str) -> int:
    by = parse_sector_export(cfg, path)
    gen = iso(now_vn())
    n = 0
    for d, rows in sorted(by.items()):
        snap = build_sector_snapshot(cfg, d, rows, gen, origin, str(path))
        p = cfg.data_dir / "snapshots" / d.isoformat() / "_SECTORS.json"
        old = read_json(p)
        if old and old["meta"]["content_hash"] == snap["meta"]["content_hash"]:
            continue
        if old and old["meta"]["origin"] == "live" and origin == "backfill":
            continue
        write_json(p, snap)
        n += 1
    return n

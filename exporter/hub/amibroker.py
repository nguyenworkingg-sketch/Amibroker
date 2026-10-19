"""Ket noi AmiBroker qua OLE/COM (pywin32) - chi chay tren Windows co AmiBroker ban quyen.

Moi Exploration chay trong 1 TIEN TRINH CON (python -m hub.amibroker job.json) de tien trinh cha
ap dung timeout cung (lenh COM dong bo khong ngat duoc tu ben trong).

Hai che do:
  * APX  (AnalysisDocs.Open(apx) -> Run(1) -> cho IsBusy -> Export) neu chien luoc co file .apx
  * AFL  (doi tuong Analysis: LoadFormula -> [Scan] -> Explore -> Export) - mac dinh, dung file Hub_*.afl
Khong ghi gi vao database AmiBroker (chi Scan/Explore/Export).
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

EXPORTER_DIR = Path(__file__).resolve().parent.parent


class AmiBrokerError(Exception):
    pass


# ---------------------------------------------------------------------- phia tien trinh cha
def run_job(job: dict, timeout: int) -> dict:
    """Chay 1 job trong tien trinh con, timeout giay. Tra ve dict ket qua cua worker."""
    jf = Path(job["out_csv"]).with_suffix(".job.json")
    jf.parent.mkdir(parents=True, exist_ok=True)
    jf.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    try:
        p = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), str(jf)], cwd=str(EXPORTER_DIR),
                           capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        raise AmiBrokerError(f"Qua thoi gian {timeout}s khi chay {Path(job['afl'] or job.get('apx') or '').name}") from e
    finally:
        try:
            jf.unlink()
        except OSError:
            pass
    lines = [ln for ln in p.stdout.splitlines() if ln.startswith("{")]
    if p.returncode != 0 or not lines:
        raise AmiBrokerError(f"Worker loi (ma {p.returncode}): {(p.stderr or p.stdout).strip()[-800:]}")
    res = json.loads(lines[-1])
    if not res.get("ok"):
        raise AmiBrokerError(res.get("error", "loi khong ro"))
    return res


def probe(database: str, benchmark: str, workdir: Path, timeout: int = 120) -> dict:
    """Kiem tra AmiBroker: database dang mo + ngay nen cuoi cua benchmark."""
    return run_job({"kind": "probe", "database": database, "benchmark": benchmark,
                    "out_csv": str(Path(workdir) / "probe.csv"), "afl": None}, timeout)


# ---------------------------------------------------------------------- phia tien trinh con
def _app(database: str | None):
    import win32com.client  # noqa: import tai cho - chi co tren Windows
    ab = win32com.client.Dispatch("Broker.Application")
    try:
        if not ab.Visible:
            ab.Visible = 1  # khong de lai ban AmiBroker an (giong scripts\run_afl.vbs)
    except Exception:
        pass
    if database:
        cur = str(ab.DatabasePath or "").rstrip("\\/")
        if not cur or Path(cur).resolve() != Path(database).resolve():
            if not ab.LoadDatabase(database):
                raise AmiBrokerError(f"Khong mo duoc database {database}")
    return ab


def _com_date(d: dt.date, end: bool = False):
    """Ngay COM (OLE DATE) KHONG qua chuyen doi mui gio: pywintypes.Time co the coi datetime la UTC va
    lech sang ngay truoc o gio VN. Dung pywintypes.Time voi tzinfo UTC + gio cuc bo co dinh -> giu nguyen ngay."""
    import pywintypes
    t = dt.datetime(d.year, d.month, d.day, 23, 59, 59) if end else dt.datetime(d.year, d.month, d.day)
    return pywintypes.Time(t.replace(tzinfo=dt.timezone.utc))


def _last_bar(ab, symbol: str) -> str | None:
    st = ab.Stocks(symbol)
    q = st.Quotations
    n = q.Count
    if n <= 0:
        return None
    d = q(n - 1).Date
    return dt.date(d.year, d.month, d.day).isoformat()


def _set_watchlist_filter(aa, n: int) -> None:
    # Filter la thuoc tinh co tham so: Filter(nType, "watchlist") = n  (nType 0 = include)
    import pythoncom
    dispid = aa._oleobj_.GetIDsOfNames("Filter")
    aa._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYPUT, False, 0, "watchlist", n)


def _worker(job: dict) -> dict:
    import pythoncom
    pythoncom.CoInitialize()
    ab = _app(job.get("database"))
    if job.get("kind") == "probe":
        return {"ok": True, "database": str(ab.DatabasePath), "last_bar": _last_bar(ab, job["benchmark"]),
                "version": str(getattr(ab, "Version", ""))}
    out = str(Path(job["out_csv"]).resolve())
    t0 = time.time()
    if job.get("apx"):
        doc = ab.AnalysisDocs.Open(job["apx"])
        if doc is None:
            raise AmiBrokerError(f"Khong mo duoc {job['apx']}")
        try:
            doc.Run(1)  # 1 = Exploration
            while doc.IsBusy:
                time.sleep(0.5)
            if not doc.Export(out):
                raise AmiBrokerError("AnalysisDoc.Export that bai")
        finally:
            doc.Close()
        return {"ok": True, "seconds": round(time.time() - t0, 1), "out": out, "mode": "apx"}
    aa = ab.Analysis
    aa.ClearFilters()
    ap = job.get("apply_to", "all")
    if ap.startswith("watchlist:"):
        aa.ApplyTo = 2
        _set_watchlist_filter(aa, int(ap.split(":")[1]))
    else:
        aa.ApplyTo = 0
    if not aa.LoadFormula(job["afl"]):
        raise AmiBrokerError(f"Khong nap duoc cong thuc {job['afl']}")
    if job.get("two_pass"):
        aa.RangeMode = 0
        aa.Scan()
    mode = job.get("range", "last")
    if mode == "range":
        aa.RangeMode = 3
        aa.RangeFromDate = _com_date(dt.date.fromisoformat(job["from"]))
        aa.RangeToDate = _com_date(dt.date.fromisoformat(job["to"]), end=True)
        got = (str(aa.RangeFromDate)[:10], str(aa.RangeToDate)[:10])
        if got != (job["from"], job["to"]):
            raise AmiBrokerError(f"Dat khoang ngay that bai: AmiBroker nhan {got}, can {job['from']}..{job['to']}")
    elif mode == "all":
        aa.RangeMode = 0
    else:
        aa.RangeMode = 1  # n phien cuoi
        aa.RangeN = 1
    aa.Explore()
    if Path(out).exists():
        Path(out).unlink()
    aa.Export(out)
    if not Path(out).exists():
        raise AmiBrokerError("Analysis.Export khong tao file")
    return {"ok": True, "seconds": round(time.time() - t0, 1), "out": out, "mode": "afl"}


if __name__ == "__main__":
    try:
        job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        res = _worker(job)
    except Exception as e:  # tra loi ro rang cho tien trinh cha
        res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0 if res.get("ok") else 1)

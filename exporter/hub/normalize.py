"""Kiem tra + chuan hoa file CSV Exploration ve schema chung cua Hub.

Dung CHUNG cho ca 2 duong vao: xuat tu dong qua COM va nhap tay CSV.
"""
from __future__ import annotations

import datetime as dt
import operator
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Strategy
from .csvio import CsvTable, parse_num, read_table
from .util import clean_number, dumps, parse_date, sha256_text

TICKER_RE = re.compile(r"^[A-Z0-9_.\-]{2,20}$")
OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq, "!=": operator.ne}
SCHEMA_VERSION = 1


class ValidationError(Exception):
    """File xuat khong hop le -> KHONG duoc dung de thay du lieu hop le."""


@dataclass
class ParsedExport:
    strategy_id: str
    path: str
    by_date: dict[dt.date, list[dict]]
    rows_total: int
    rows_passing: int
    warnings: list[str] = field(default_factory=list)
    encoding: str = "utf-8"


def _metric_value(raw: str | None, unit: str | None, decimal: str):
    if raw is None:
        return None
    if unit == "text":
        t = raw.strip()
        return t if t and t != "-" else None
    v = parse_num(raw, decimal)
    if unit == "bool":
        return None if v is None else bool(v)
    return clean_number(v, 4)


def check_pass(rule: dict | None, row: list[str], table: CsvTable) -> bool:
    if not rule:
        return True
    i = table.col_index(rule["column"])
    if i is None:
        raise ValidationError(f"Thieu cot '{rule['column']}' dung trong quy tac dat")
    v = parse_num(row[i] if i < len(row) else None, table.decimal)
    if v is None:
        return False
    return OPS[rule.get("op", ">=")](v, float(rule["value"]))


def parse_export(strategy: Strategy, path: str | Path, session: dt.date | None = None,
                 only_session: bool = False) -> ParsedExport:
    """Doc file xuat. `session` bat buoc neu chien luoc khong co cot ngay (chi tinh phien cuoi).
    only_session=True: chi giu dong co ngay == session (dung khi chay 'phien cuoi' cho ma ngung giao dich)."""
    path = Path(path)
    if not path.exists():
        raise ValidationError(f"Khong thay file xuat: {path}")
    if path.stat().st_size == 0:
        raise ValidationError(f"File xuat rong (0 byte): {path.name}")
    t = read_table(path)
    if not t.header:
        raise ValidationError(f"File khong co dong tieu de: {path.name}")
    cols = strategy.columns
    i_t = t.col_index(cols.get("ticker"))
    i_s = t.col_index(cols.get("score"))
    i_d = t.col_index(cols.get("date"))
    missing = [n for n, i in (("ticker", i_t), ("score", i_s)) if i is None]
    if cols.get("date") and i_d is None:
        missing.append("date")
    if missing:
        raise ValidationError(f"{strategy.id}: thieu cot {', '.join(f'{m}={cols.get(m)!r}' for m in missing)}; "
                              f"tieu de file: {t.header[:12]}")
    if i_d is None and session is None:
        raise ValidationError(f"{strategy.id}: file khong co cot ngay -> phai chi ro phien (--session)")
    i_sc = t.col_index(cols.get("state_code"))
    i_st = t.col_index(cols.get("state"))
    mcols = [(m, t.col_index(m["col"])) for m in strategy.metrics]
    warns = list(t.warnings)
    for m, i in mcols:
        if i is None:
            warns.append(f"Khong co cot phu '{m['col']}' -> de trong")
    by_date: dict[dt.date, list[dict]] = {}
    seen: set[tuple[str, dt.date]] = set()
    bad_ticker = bad_date = dup = 0
    n_pass = 0
    for row in t.rows:
        if len(row) < len(t.header):
            row = row + [""] * (len(t.header) - len(row))
        tk = row[i_t].strip().upper()
        if not TICKER_RE.match(tk):
            bad_ticker += 1
            continue
        d = parse_date(row[i_d]) if i_d is not None else session
        if d is None:
            bad_date += 1
            continue
        if session is not None and d > session:
            raise ValidationError(f"{strategy.id}: co dong ngay {d} SAU phien {session} -> du lieu trong phien/chua chot?")
        if only_session and d != session:
            continue
        if not check_pass(strategy.pass_rule, row, t):
            continue
        if (tk, d) in seen:
            dup += 1
            continue
        seen.add((tk, d))
        sc = parse_num(row[i_sc], t.decimal) if i_sc is not None else None
        st_text = row[i_st].strip() if i_st is not None else ""
        code = int(sc) if sc is not None else None
        label = strategy.state_labels.get(code) if code is not None else None
        rec = {
            "ticker": tk,
            "state_code": code,
            "state": label or (st_text if st_text and st_text != "-" else None),
            "strategy_score": clean_number(parse_num(row[i_s], t.decimal), 3),
            "additional_metrics": {m["key"]: _metric_value(row[i] if i is not None else None, m.get("unit"), t.decimal)
                                   for m, i in mcols},
        }
        by_date.setdefault(d, []).append(rec)
        n_pass += 1
    if bad_ticker:
        warns.append(f"Bo {bad_ticker} dong ma khong hop le")
    if bad_date:
        warns.append(f"Bo {bad_date} dong khong doc duoc ngay")
    if dup:
        warns.append(f"Bo {dup} dong trung (ma, ngay)")
    if bad_ticker and bad_ticker > 0.2 * max(1, len(t.rows)):
        raise ValidationError(f"{strategy.id}: {bad_ticker}/{len(t.rows)} dong ma khong hop le -> file loi?")
    return ParsedExport(strategy.id, str(path), by_date, len(t.rows), n_pass, warns, t.encoding)


def rank_records(recs: list[dict]) -> list[dict]:
    """Sap theo diem giam dan (thieu diem xep cuoi), cung diem -> cung hang (1,2,2,4)."""
    recs = sorted(recs, key=lambda r: (r["strategy_score"] is None, -(r["strategy_score"] or 0), r["ticker"]))
    prev_score, prev_rank = object(), 0
    for i, r in enumerate(recs, 1):
        s = r["strategy_score"]
        if s is None:
            r["strategy_rank"] = None
            continue
        r["strategy_rank"] = prev_rank if s == prev_score else i
        prev_score, prev_rank = s, r["strategy_rank"]
    return recs


def build_snapshot(strategy: Strategy, session: dt.date, recs: list[dict], market=None, *, origin: str,
                   source_file: str, source_sha256: str | None, generated_at: str, data_asof: str | None = None,
                   warnings: list[str] | None = None) -> dict:
    """Snapshot = ket qua 1 chien luoc x 1 phien, da lam giau bang du lieu thi truong TAI phien do."""
    out = []
    for r in rank_records([dict(x) for x in recs]):
        e = market.enrich(r["ticker"], session) if market is not None else {}
        out.append({
            "ticker": r["ticker"],
            "strategy_id": strategy.id,
            "signal_date": session.isoformat(),
            "state_code": r["state_code"],
            "state": r["state"],
            "strategy_score": r["strategy_score"],
            "strategy_rank": r["strategy_rank"],
            "name": e.get("name"),
            "exchange": e.get("exchange"),
            "sector": e.get("sector"),
            "close": clean_number(e.get("close"), 3),
            "ret_1d": clean_number(e.get("ret_1d"), 2),
            "ret_5d": clean_number(e.get("ret_5d"), 2),
            "ret_20d": clean_number(e.get("ret_20d"), 2),
            "avg_trading_value_20": clean_number(e.get("avg_trading_value_20"), 2),
            "relative_strength_score": clean_number(e.get("relative_strength_score"), 1),
            "additional_metrics": r["additional_metrics"],
        })
    content_hash = sha256_text(dumps(out))
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "strategy_id": strategy.id,
            "strategy_version": strategy.version,
            "session": session.isoformat(),
            "data_asof": data_asof or session.isoformat(),
            "generated_at": generated_at,
            "origin": origin,
            "source_file": Path(source_file).name,
            "source_sha256": source_sha256,
            "pass_rule": strategy.pass_rule,
            "record_count": len(out),
            "content_hash": content_hash,
            "revision": 1,
            "warnings": warnings or [],
        },
        "records": out,
    }

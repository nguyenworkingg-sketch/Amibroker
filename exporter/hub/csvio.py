"""Doc file CSV xuat tu AmiBroker (hoac nhap tay) mot cach an toan.

Xu ly ro rang: ma hoa (UTF-8 co/khong BOM, Windows-1258, Windows-1252), dau phan cach
(, ; tab), dau thap phan (. hoac ,), ten cot lech hoa/thuong/khoang trang, gia tri thieu.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

MISSING = {"", "-", "n/a", "na", "nan", "null", "none", "{empty}", "#n/a", "inf", "-inf"}
ENCODINGS = ("utf-8-sig", "cp1258", "cp1252", "latin-1")


@dataclass
class CsvTable:
    path: str
    encoding: str
    delimiter: str
    decimal: str
    header: list[str]
    rows: list[list[str]]
    warnings: list[str] = field(default_factory=list)

    def col_index(self, name: str | None) -> int | None:
        if not name:
            return None
        key = norm_col(name)
        for i, h in enumerate(self.header):
            if norm_col(h) == key:
                return i
        return None


def norm_col(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).replace("﻿", "")).strip().lower()


def _decode(raw: bytes) -> tuple[str, str]:
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1"


def _sniff_delimiter(first_line: str) -> str:
    counts = {d: first_line.count(d) for d in (",", ";", "\t")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def read_table(path: str | Path) -> CsvTable:
    path = Path(path)
    raw = path.read_bytes()
    text, enc = _decode(raw)
    text = unicodedata.normalize("NFC", text)  # Windows-1258 dung dau to hop
    lines = text.splitlines()
    first = next((ln for ln in lines if ln.strip()), "")
    delim = _sniff_delimiter(first)
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    all_rows = [r for r in reader if any(c.strip() for c in r)]
    header = [h.replace("﻿", "").strip() for h in all_rows[0]] if all_rows else []
    rows = all_rows[1:]
    decimal = "," if delim != "," and _looks_decimal_comma(rows) else "."
    t = CsvTable(str(path), enc, delim, decimal, header, rows)
    # AmiBroker them dau phan cach cuoi dong -> cot rong cuoi
    while t.header and t.header[-1] == "" and all(len(r) <= len(t.header) and (len(r) < len(t.header) or r[-1].strip() == "") for r in rows):
        t.header.pop()
        t.rows = [r[: len(t.header)] for r in t.rows]
    bad = [i for i, r in enumerate(t.rows) if len(r) != len(t.header)]
    if bad:
        t.warnings.append(f"{len(bad)} dong co so cot khac tieu de (dong dau: {bad[0] + 2})")
    return t


def _looks_decimal_comma(rows: list[list[str]]) -> bool:
    pat = re.compile(r"^-?\d+,\d+$")
    n = sum(1 for r in rows[:50] for c in r if pat.match(c.strip()))
    return n > 0


def parse_num(s: str | None, decimal: str = ".") -> float | None:
    """So hoc tu chuoi; gia tri thieu -> None (KHONG ep thanh 0)."""
    if s is None:
        return None
    t = str(s).strip().replace(" ", "").replace(" ", "")
    if t.lower() in MISSING:
        return None
    pct = t.endswith("%")
    if pct:
        t = t[:-1]
    if decimal == ",":
        t = t.replace(".", "").replace(",", ".")
    else:
        if "," in t and "." in t:
            t = t.replace(",", "")
        elif "," in t:
            # "1,234" (nghin) vs "1,5" (thap phan): 3 chu so sau dau phay -> phan nghin
            parts = t.split(",")
            if all(len(p) == 3 for p in parts[1:]):
                t = t.replace(",", "")
            else:
                t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    # AmiBroker dung -1e10 lam gia tri Null noi bo (va 1e30 trong mot so ham)
    if abs(v) >= 1e10:
        return None
    return v

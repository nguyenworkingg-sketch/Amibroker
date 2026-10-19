"""Tien ich chung: thoi gian VN, ghi file nguyen tu (atomic), JSON tat dinh, hash."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

# Viet Nam khong co gio mua he -> offset co dinh, khong can tzdata tren Windows
VN_TZ = dt.timezone(dt.timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def now_vn() -> dt.datetime:
    return dt.datetime.now(VN_TZ).replace(microsecond=0)


def iso(t: dt.datetime) -> str:
    return t.astimezone(VN_TZ).isoformat()


def clean_number(x: Any, ndigits: int | None = None) -> Any:
    """NaN/inf -> None (JSON null). Khong bao gio ep gia tri thieu thanh 0."""
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    try:
        f = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(f) or math.isinf(f):
        return None
    if ndigits is not None:
        f = round(f, ndigits)
        if f == 0:
            f = 0.0  # tranh -0.0
    return f


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        return clean_number(obj)
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):  # numpy scalar
        try:
            return _sanitize(obj.item())
        except Exception:  # pragma: no cover
            return obj
    return obj


def dumps(obj: Any, compact: bool = True) -> str:
    """JSON tat dinh: cung du lieu vao -> cung chuoi ra (thu tu khoa giu nguyen theo cach tao)."""
    obj = _sanitize(obj)
    if compact:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json(path: Path, obj: Any, compact: bool = True) -> bool:
    """Ghi JSON nguyen tu. Tra ve False neu noi dung khong doi (khong ghi lai)."""
    text = dumps(obj, compact=compact) + "\n"
    path = Path(path)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == text:
                return False
        except OSError:
            pass
    atomic_write_text(path, text)
    return True


def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_date(s: Any) -> dt.date | None:
    """Ngay tu nhieu dinh dang: YYYY-MM-DD, DateNum AmiBroker (1261016), YYYYMMDD, dd/mm/yyyy."""
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        return s.date()
    if isinstance(s, dt.date):
        return s
    t = str(s).strip()
    if not t:
        return None
    try:
        f = float(t)
        n = int(f)
        if f == n:
            if 1_000_000 <= n < 2_000_000:  # AmiBroker DateNum = 10000*(nam-1900)+100*thang+ngay
                n += 19_000_000
            if 19_000_000 <= n < 30_000_000:
                return dt.date(n // 10000, (n // 100) % 100, n % 100)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return dt.datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None

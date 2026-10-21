"""Thong bao Telegram cho Top RS (ma moi vao / roi top).

Bi mat (token bot) nam NGOAI repo: duong dan cau hinh = settings.notify.telegram_config (mac dinh
D:\\AmiBroker_VN\\config\\telegram.ini). Khong bao gio in / ghi log token.
Chong gui trung: archive/notify/sent_<YYYY-MM-DD>.json luu cac khoa da gui trong ngay.
"""
from __future__ import annotations

import configparser
import html
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import Config
from .util import now_vn, read_json, write_json

log = logging.getLogger("hub")
SITE = "https://nguyenworkingg-sketch.github.io/Amibroker/"


class Telegram:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.path = Path(cfg.settings.get("notify", {}).get("telegram_config", r"D:\AmiBroker_VN\config\telegram.ini"))
        self.ini = configparser.ConfigParser()
        if self.path.exists():
            self.ini.read(self.path, encoding="utf-8-sig")
        sec = self.ini["telegram"] if self.ini.has_section("telegram") else {}
        self.token = (sec.get("bot_token") or "").strip()
        self.chat_id = (sec.get("chat_id") or "").strip()
        self.flags = {k: str(sec.get(k, "1")).strip() == "1" for k in ("eod", "intraday")}
        self.every = int(sec.get("intraday_every_min", "15") or 15)

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _api(self, method: str, data: dict | None = None) -> dict:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        body = urllib.parse.urlencode(data).encode() if data else None
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:  # khong de token lot vao thong bao loi
            return {"ok": False, "description": f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}"}
        except OSError as e:
            return {"ok": False, "description": f"{type(e).__name__}"}

    def ensure_chat_id(self) -> str | None:
        """Lay chat_id tu tin nhan gan nhat nguoi dung gui cho bot (sau khi bam Start) va luu vao file cau hinh."""
        if self.chat_id:
            return self.chat_id
        r = self._api("getUpdates")
        if not r.get("ok"):
            log.warning("Telegram getUpdates loi: %s", r.get("description"))
            return None
        chats = [u.get("message", {}).get("chat", {}).get("id") for u in r.get("result", []) if u.get("message")]
        chats = [c for c in chats if c]
        if not chats:
            log.warning("Telegram: chua co tin nhan nao gui toi bot -> mo bot va bam Start")
            return None
        self.chat_id = str(chats[-1])
        text = self.path.read_text(encoding="utf-8-sig")
        lines = [f"chat_id = {self.chat_id}" if ln.strip().startswith("chat_id") else ln for ln in text.splitlines()]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.chat_id

    def send(self, text: str) -> bool:
        if not self.configured or not self.ensure_chat_id():
            return False
        r = self._api("sendMessage", {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                                      "disable_web_page_preview": "true"})
        if not r.get("ok"):
            log.warning("Telegram gui loi: %s", r.get("description"))
        return bool(r.get("ok"))


def _sent_path(cfg: Config, day: str) -> Path:
    return cfg.archive_dir / "notify" / f"sent_{day}.json"


def _fmt_pct(x) -> str:
    return "—" if x is None else f"{x:+.1f}%".replace(".", ",")


def _fmt_int(x) -> str:
    return "—" if x is None else f"{float(x):.0f}"


def _fmt_px(x) -> str:
    return "—" if x is None else f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _line_enter(r: dict) -> str:
    t = html.escape(r["ticker"])
    return (f'• <b>{t}</b> {html.escape(r.get("sector") or "")} — '
            f'SM trung hạn <b>{_fmt_int(r.get("sm_mid"))}</b>, ngắn hạn {_fmt_int(r.get("sm_short"))}'
            f' · giá {_fmt_px(r.get("price"))}')


def _line_exit(r: dict) -> str:
    t = html.escape(r["ticker"])
    why = "mất thanh khoản" if r.get("exit_reason") == "illiquid" else f"SM {r.get('sm_mid_exit', '—')}"
    return (f'• <b>{t}</b> ({why}) — ở top {r.get("sessions")} phiên, từ khi vào {_fmt_pct(r.get("ret_pct"))}'
            f' (VNI {_fmt_pct(r.get("vni_ret_pct"))})')


def eod_toprs(cfg: Config, doc: dict, tg: Telegram | None = None, dry_run: bool = False) -> str | None:
    """Tin cuoi ngay tu data/toprs/latest.json. Moi phien gui 1 lan."""
    if not doc or not doc.get("available"):
        return None
    tg = tg or Telegram(cfg)
    s, rule, day = doc["summary"], doc["rule"], doc["session"]
    sent = read_json(_sent_path(cfg, day), {})
    if sent.get("eod") and not dry_run:
        return None
    new = [r for r in doc["rows"] if r.get("new_today")]
    exits = [r for r in doc.get("recent_exits", []) if r.get("exit_date") == day]
    d = "/".join(reversed(day.split("-")))
    parts = [f"<b>Top RS — phiên {d}</b> (chốt cuối ngày)",
             f"Trong top: <b>{s['in_top']}</b> mã · rổ {s['universe']} mã GTGD20 ≥ {rule['min_value_bil']:.0f} tỷ · "
             f"vào ≥ {rule['enter']:.0f}, rời &lt; {rule['exit']:.0f}"]
    parts.append(f"\n🟢 <b>Mới vào ({len(new)})</b>" + ("\n" + "\n".join(_line_enter(r) for r in new) if new else ": không có"))
    parts.append(f"\n🔴 <b>Rời top ({len(exits)})</b>" + ("\n" + "\n".join(_line_exit(r) for r in exits) if exits else ": không có"))
    if s.get("median_ret_pct") is not None:
        parts.append(f"\nDanh sách đang lãi {s['pct_positive']:.0f}% · trung vị từ khi vào {_fmt_pct(s['median_ret_pct'])}")
    parts.append(f'<a href="{SITE}#/top-rs">Xem bảng Top RS</a>')
    text = "\n".join(parts)
    if dry_run:
        return text
    if tg.flags.get("eod", True) and tg.send(text):
        sent["eod"] = now_vn().isoformat()
        write_json(_sent_path(cfg, day), sent, compact=False)
        return text
    return None


def intraday_alerts(cfg: Config, enters: list[dict], exits: list[dict], asof: str, tg: Telegram | None = None,
                    dry_run: bool = False) -> str | None:
    """Canh bao trong phien: chi gui ma CHUA bao hom nay (moi ma / loai toi da 1 lan / ngay)."""
    tg = tg or Telegram(cfg)
    day = now_vn().date().isoformat()
    sent = read_json(_sent_path(cfg, day), {})
    keys = set(sent.get("intraday", []))
    new_e = [r for r in enters if f"enter:{r['ticker']}" not in keys]
    new_x = [r for r in exits if f"exit:{r['ticker']}" not in keys]
    if not new_e and not new_x:
        return None
    parts = [f"<b>Top RS trong phiên — {html.escape(asof)}</b> (ước tính trên giá tạm, chốt cuối ngày)"]
    if new_e:
        parts.append("🟢 <b>Sắp vào top</b>\n" + "\n".join(_line_enter(r) for r in new_e))
    if new_x:
        parts.append("🔴 <b>Có thể rời top</b>\n" + "\n".join(
            f'• <b>{html.escape(r["ticker"])}</b> — SM trung hạn ước tính <b>{_fmt_int(r.get("sm_mid"))}</b> (&lt; {_fmt_int(r.get("exit"))}), giá {_fmt_px(r.get("price"))}'
            for r in new_x))
    text = "\n\n".join(parts)
    if dry_run:
        return text
    if tg.flags.get("intraday", True) and tg.send(text):
        sent["intraday"] = sorted(keys | {f"enter:{r['ticker']}" for r in new_e} | {f"exit:{r['ticker']}" for r in new_x})
        write_json(_sent_path(cfg, day), sent, compact=False)
        return text
    return None

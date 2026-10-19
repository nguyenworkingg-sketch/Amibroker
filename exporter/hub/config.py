"""Nap cau hinh (strategy_config.yaml) + ghi de bang bien moi truong."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

EXPORTER_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = EXPORTER_DIR.parent
DEFAULT_CONFIG = EXPORTER_DIR / "strategy_config.yaml"

ENV_OVERRIDES = {
    "HUB_AB_DATABASE": ("amibroker", "database"),
    "HUB_FORMULAS_DIR": ("amibroker", "formulas_dir"),
    "HUB_IMPORT_DIR": ("market_data", "import_dir"),
    "HUB_SECTOR_MAP": ("market_data", "sector_map"),
}


@dataclass
class Strategy:
    id: str
    name_vi: str
    description: str
    enabled: bool
    version: str
    afl: str | None
    source_afl: list[str]
    apx: str | None
    apply_to: str
    two_pass: bool
    supports_backfill: bool
    columns: dict[str, str | None]
    pass_rule: dict[str, Any] | None
    score_name: str
    scoring: str
    state_labels: dict[int, str]
    metrics: list[dict[str, str]]
    raw: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        """Thong tin dang len web (khong co duong dan may)."""
        return {
            "id": self.id,
            "name": self.name_vi,
            "description": self.description,
            "enabled": self.enabled,
            "version": self.version,
            "source_afl": self.source_afl,
            "adapter_afl": self.afl,
            "apx": Path(self.apx).name if self.apx else None,
            "two_pass": self.two_pass,
            "supports_backfill": self.supports_backfill,
            "pass_rule": self.pass_rule,
            "score_name": self.score_name,
            "scoring": self.scoring,
            "state_labels": {str(k): v for k, v in self.state_labels.items()},
            "metrics": [{"key": m["key"], "label": m["label"], "unit": m.get("unit")} for m in self.metrics],
        }


@dataclass
class Config:
    path: Path
    settings: dict[str, Any]
    strategies: list[Strategy]
    auxiliary: list[dict[str, Any]]
    sector_names: dict[str, str]
    data_dir: Path
    archive_dir: Path

    def strategy(self, sid: str) -> Strategy:
        for s in self.strategies:
            if s.id == sid.upper():
                return s
        raise KeyError(f"Khong co chien luoc '{sid}' trong {self.path.name}")

    def enabled(self) -> list[Strategy]:
        return [s for s in self.strategies if s.enabled]

    def sector_vi(self, name: str | None) -> str | None:
        if not name:
            return None
        return self.sector_names.get(name, name)


def load_config(path: str | Path | None = None, data_dir: str | Path | None = None,
                archive_dir: str | Path | None = None) -> Config:
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    settings = raw.get("settings", {})
    for env, (sec, key) in ENV_OVERRIDES.items():
        if os.environ.get(env):
            settings.setdefault(sec, {})[key] = os.environ[env]
    strategies = []
    seen = set()
    for s in raw.get("strategies", []):
        sid = str(s["id"]).upper()
        if sid in seen:
            raise ValueError(f"Trung ID chien luoc: {sid}")
        seen.add(sid)
        strategies.append(Strategy(
            id=sid,
            name_vi=s.get("name_vi", sid),
            description=s.get("description", ""),
            enabled=bool(s.get("enabled", True)),
            version=str(s.get("version", "1.0")),
            afl=s.get("afl"),
            source_afl=list(s.get("source_afl") or []),
            apx=s.get("apx"),
            apply_to=str(s.get("apply_to", "all")),
            two_pass=bool(s.get("two_pass", False)),
            supports_backfill=bool(s.get("supports_backfill", False)),
            columns=dict(s.get("columns") or {}),
            pass_rule=s.get("pass_rule"),
            score_name=s.get("score_name", "Điểm"),
            scoring=s.get("scoring", ""),
            state_labels={int(k): str(v) for k, v in (s.get("state_labels") or {}).items()},
            metrics=list(s.get("metrics") or []),
            raw=s,
        ))
        if not strategies[-1].columns.get("ticker") or not strategies[-1].columns.get("score"):
            raise ValueError(f"{sid}: columns.ticker va columns.score la bat buoc")
    dd = Path(data_dir or os.environ.get("HUB_DATA_DIR") or REPO_ROOT / "data")
    ad = Path(archive_dir or os.environ.get("HUB_ARCHIVE_DIR") or REPO_ROOT / "archive")
    return Config(path, settings, strategies, list(raw.get("auxiliary") or []),
                  dict((raw.get("sectors") or {}).get("names_vi") or {}), dd, ad)

from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import yaml

from .paths import config_path, user_config_dir

DEFAULT_CONFIG = {
    "check_interval_seconds": 10,
    "touch_rules": {
        "content_hash": True,
        "metadata": True,
        "existence": True,
    },
    "notifications": {
        "enabled": True,
        "min_severity": "medium",
    },
}

def load_config() -> dict:
    p = config_path()
    if not p.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # merge defaults (shallow + nested)
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in data.items() if k in merged})
    for nk in ("touch_rules", "notifications"):
        merged[nk] = dict(DEFAULT_CONFIG[nk])
        merged[nk].update((data.get(nk) or {}))
    return merged

def save_config(cfg: dict) -> None:
    d = user_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    p = config_path()
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

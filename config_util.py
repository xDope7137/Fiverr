"""Shared config loader. Every script reads `config.json` through this so a
single edit changes defaults everywhere.

CLI flags on each script still override values loaded from config.
"""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    "serial": None,
    "message": "Hello",
    "send": False,
    "min_interval_seconds": 60.0,
    "max_interval_seconds": 180.0,
    "max_replies_per_scan": 5,
}


def load_config():
    """Return a dict with every DEFAULTS key present.

    Creates config.json with defaults on first call if it's missing.
    Falls back to defaults (without overwriting) if the file is malformed.
    """
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULTS)
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def resolve_serial(cli_serial):
    """CLI > config.json. Returns None if neither set (uiautomator2 will then
    auto-detect a single attached device)."""
    if cli_serial:
        return cli_serial
    return load_config().get("serial")

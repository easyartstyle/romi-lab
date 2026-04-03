from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION"
RELEASE_CONFIG_FILE = ROOT / "release_config.json"
DEFAULT_VERSION = "0.1.0"
DEFAULT_RELEASE_CONFIG = {
    "app_name": "ROMI Lab",
    "publisher": "easyartstyle",
    "github_owner": "",
    "github_repo": "",
    "update_check_enabled": True,
    "release_api_template": "https://api.github.com/repos/{owner}/{repo}/releases/latest",
    "release_page_template": "https://github.com/{owner}/{repo}/releases/latest",
}


def load_app_version() -> str:
    try:
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
        return value or DEFAULT_VERSION
    except Exception:
        return DEFAULT_VERSION


def load_release_config() -> dict:
    config = dict(DEFAULT_RELEASE_CONFIG)
    try:
        if RELEASE_CONFIG_FILE.exists():
            loaded = json.loads(RELEASE_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
    except Exception:
        pass
    return config


def normalize_version(value: str) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    return text or DEFAULT_VERSION


def version_tuple(value: str) -> tuple[int, ...]:
    normalized = normalize_version(value)
    parts: list[int] = []
    for part in normalized.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer_version(latest: str, current: str) -> bool:
    return version_tuple(latest) > version_tuple(current)


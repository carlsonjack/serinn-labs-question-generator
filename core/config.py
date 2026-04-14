"""Load global settings from YAML with optional local overrides and env API key."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_SETTINGS = _ROOT / "config" / "settings.yaml"
_SETTINGS_LOCAL = _ROOT / "config" / "settings.local.yaml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge nested mapping values without discarding sibling keys."""

    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings() -> dict[str, Any]:
    if not _SETTINGS.is_file():
        raise FileNotFoundError(f"Missing config file: {_SETTINGS}")

    with _SETTINGS.open(encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    if _SETTINGS_LOCAL.is_file():
        with _SETTINGS_LOCAL.open(encoding="utf-8") as f:
            local = yaml.safe_load(f) or {}
        if isinstance(local, dict):
            data = _deep_merge(data, local)

    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        data["openai_api_key"] = env_key

    return data

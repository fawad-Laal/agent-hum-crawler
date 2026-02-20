"""Centralized feature-flag loader for runtime and dashboard behavior."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_FEATURE_FLAGS: dict[str, Any] = {
    "reliefweb_enabled": True,
    "llm_enrichment_enabled": False,
    "report_strict_filters_default": True,
    "dashboard_auto_source_check_default": True,
    "source_check_endpoint_enabled": True,
    "max_item_age_days_default": 30,
    "stale_feed_auto_warn_enabled": True,
    "stale_feed_auto_demote_enabled": False,
    "stale_feed_warn_after_checks": 2,
    "stale_feed_demote_after_checks": 5,
}


def default_feature_flags_path() -> Path:
    return Path.cwd() / "config" / "feature_flags.json"


def _coerce_flag_value(key: str, value: Any) -> Any:
    default = DEFAULT_FEATURE_FLAGS.get(key)
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        raw = str(value).strip().lower()
        return raw in {"1", "true", "yes", "on"}
    if isinstance(default, int):
        try:
            return int(value)
        except Exception:
            return default
    return value


def load_feature_flags(path: Path | None = None) -> dict[str, Any]:
    flags = dict(DEFAULT_FEATURE_FLAGS)
    candidate = path or default_feature_flags_path()
    if candidate.exists():
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                for key in DEFAULT_FEATURE_FLAGS:
                    if key in payload:
                        flags[key] = _coerce_flag_value(key, payload[key])
        except Exception:
            pass

    # Legacy env compatibility.
    legacy_map = {
        "RELIEFWEB_ENABLED": "reliefweb_enabled",
        "LLM_ENRICHMENT_ENABLED": "llm_enrichment_enabled",
    }
    for env_key, flag_key in legacy_map.items():
        raw = os.getenv(env_key, "").strip()
        if raw:
            flags[flag_key] = _coerce_flag_value(flag_key, raw)

    # New explicit env override: AHC_FLAG_<FLAG_NAME_UPPER>
    for key in DEFAULT_FEATURE_FLAGS:
        env_key = f"AHC_FLAG_{key.upper()}"
        raw = os.getenv(env_key, "").strip()
        if raw:
            flags[key] = _coerce_flag_value(key, raw)

    return flags


def get_feature_flag(name: str, default: Any = None) -> Any:
    flags = load_feature_flags()
    if name in flags:
        return flags[name]
    return default

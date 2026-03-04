"""GET /api/system-info, GET /api/country-sources, GET /api/feature-flags, POST /api/feature-flags."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_ROOT = Path(__file__).resolve().parents[5]
_COUNTRY_SOURCES_FILE = _ROOT / "config" / "country_sources.json"
_FEATURE_FLAGS_FILE = _ROOT / "config" / "feature_flags.json"


# ── /api/system-info ──────────────────────────────────────────────────────


@router.get("/system-info")
def system_info() -> dict:
    rust_available = False
    try:
        from agent_hum_crawler.rust_accel import rust_available as _ra  # type: ignore[import]
        rust_available = _ra()
    except ImportError:
        pass

    from agent_hum_crawler.config import ALLOWED_DISASTER_TYPES
    return {
        "python_version": sys.version,
        "rust_available": rust_available,
        "allowed_disaster_types": sorted(ALLOWED_DISASTER_TYPES),
    }


# ── /api/country-sources ─────────────────────────────────────────────────


@router.get("/country-sources")
def country_sources() -> dict:
    data: dict = {}
    try:
        data = json.loads(_COUNTRY_SOURCES_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

    countries_cfg = data.get("countries", {})
    global_cfg = data.get("global", {})
    cats = ("government", "un", "ngo", "local_news")

    summary = []
    for c in sorted(countries_cfg.keys()):
        entry = countries_cfg[c]
        feed_count = sum(len(entry.get(cat, [])) for cat in cats)
        summary.append({"country": c, "feed_count": feed_count, "sources": entry})

    global_feed_count = sum(len(global_cfg.get(cat, [])) for cat in cats)
    return {
        "countries": summary,
        "global_feed_count": global_feed_count,
        "global_sources": global_cfg,
    }


# ── /api/feature-flags ────────────────────────────────────────────────────


class FeatureFlagUpdate(BaseModel):
    flag: str
    enabled: bool


@router.get("/feature-flags")
def get_feature_flags() -> dict:
    """Return all current feature flags."""
    try:
        flags: dict = json.loads(_FEATURE_FLAGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="feature_flags.json not found")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Malformed feature_flags.json: {exc}")
    return {"feature_flags": flags}


@router.post("/feature-flags")
def update_feature_flag(body: FeatureFlagUpdate) -> dict:
    """Toggle a single feature flag and persist to feature_flags.json."""
    try:
        flags: dict = json.loads(_FEATURE_FLAGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="feature_flags.json not found")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Malformed feature_flags.json: {exc}")

    flags[body.flag] = body.enabled
    _FEATURE_FLAGS_FILE.write_text(json.dumps(flags, indent=2), encoding="utf-8")
    return {"feature_flags": {k: bool(v) for k, v in flags.items()}}

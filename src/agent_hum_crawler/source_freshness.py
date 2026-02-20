"""Source freshness state and stale feed demotion helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .feature_flags import get_feature_flag
from .time_utils import parse_published_datetime


@dataclass
class FreshnessEvaluation:
    status: str
    is_stale: bool
    age_days: float | None


def default_state_path() -> Path:
    return Path.home() / ".moltis" / "agent-hum-crawler" / "source_freshness_state.json"


def evaluate_freshness(latest_published_at: str | None, max_age_days: int | None) -> FreshnessEvaluation:
    if not latest_published_at or not max_age_days:
        return FreshnessEvaluation(status="unknown", is_stale=False, age_days=None)
    dt = parse_published_datetime(latest_published_at)
    if dt is None:
        return FreshnessEvaluation(status="unknown", is_stale=False, age_days=None)
    now = datetime.now(UTC)
    if dt > now:
        return FreshnessEvaluation(status="fresh", is_stale=False, age_days=0.0)
    age_days = (now - dt).total_seconds() / 86400.0
    is_stale = age_days > float(max_age_days)
    return FreshnessEvaluation(
        status="stale" if is_stale else "fresh",
        is_stale=is_stale,
        age_days=round(age_days, 2),
    )


def load_state(path: Path | None = None) -> dict[str, Any]:
    state_path = path or default_state_path()
    if not state_path.exists():
        return {"sources": {}}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {"sources": {}}
    if not isinstance(payload, dict):
        return {"sources": {}}
    sources = payload.get("sources", {})
    if not isinstance(sources, dict):
        sources = {}
    return {"sources": sources}


def save_state(state: dict[str, Any], path: Path | None = None) -> None:
    state_path = path or default_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def stale_policy() -> dict[str, Any]:
    return {
        "warn_enabled": bool(get_feature_flag("stale_feed_auto_warn_enabled", True)),
        "demote_enabled": bool(get_feature_flag("stale_feed_auto_demote_enabled", False)),
        "warn_after_checks": int(get_feature_flag("stale_feed_warn_after_checks", 2)),
        "demote_after_checks": int(get_feature_flag("stale_feed_demote_after_checks", 5)),
    }


def source_state(state: dict[str, Any], source_url: str) -> dict[str, Any]:
    sources = state.setdefault("sources", {})
    if source_url not in sources or not isinstance(sources[source_url], dict):
        sources[source_url] = {}
    return sources[source_url]


def should_demote(state: dict[str, Any], source_url: str) -> bool:
    policy = stale_policy()
    if not policy["demote_enabled"]:
        return False
    row = source_state(state, source_url)
    streak = int(row.get("stale_streak", 0) or 0)
    return streak >= max(1, int(policy["demote_after_checks"]))


def current_stale_action(stale_streak: int) -> str | None:
    policy = stale_policy()
    if policy["demote_enabled"] and stale_streak >= max(1, int(policy["demote_after_checks"])):
        return "demote"
    if policy["warn_enabled"] and stale_streak >= max(1, int(policy["warn_after_checks"])):
        return "warn"
    return None


def update_source_state(
    state: dict[str, Any],
    *,
    source_url: str,
    latest_published_at: str | None,
    freshness_status: str,
    status: str,
) -> dict[str, Any]:
    row = source_state(state, source_url)
    stale_streak = int(row.get("stale_streak", 0) or 0)
    if freshness_status == "stale":
        stale_streak += 1
    elif freshness_status == "fresh":
        stale_streak = 0
    row["stale_streak"] = stale_streak
    row["latest_published_at"] = latest_published_at
    row["last_status"] = status
    row["last_checked_at"] = datetime.now(UTC).isoformat()
    row["stale_action"] = current_stale_action(stale_streak)
    return row

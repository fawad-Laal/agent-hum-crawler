"""Fixture-based replay runner for QA and hardening."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .alerts import build_alert_contract
from .config import RuntimeConfig
from .dedupe import detect_changes
from .models import RawSourceItem


@dataclass
class ReplayResult:
    summary: str
    events: list
    current_hashes: list[str]
    alerts_contract: dict


def load_replay_fixture(path: str | Path) -> dict:
    fixture_path = Path(path)
    if not fixture_path.exists():
        raise FileNotFoundError(f"Replay fixture not found: {fixture_path}")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def run_replay_fixture(path: str | Path) -> ReplayResult:
    payload = load_replay_fixture(path)

    config = RuntimeConfig.model_validate(
        {
            "countries": payload.get("countries", ["Pakistan"]),
            "disaster_types": payload.get("disaster_types", ["flood"]),
            "check_interval_minutes": payload.get("check_interval_minutes", 30),
            "subregions": payload.get("subregions", {}),
            "priority_sources": payload.get("priority_sources", []),
            "quiet_hours_local": payload.get("quiet_hours_local"),
        }
    )

    raw_items = [RawSourceItem.model_validate(item) for item in payload.get("items", [])]
    previous_hashes = payload.get("previous_hashes", [])

    dedupe_result = detect_changes(
        items=raw_items,
        previous_hashes=previous_hashes,
        countries=config.countries,
        disaster_types=config.disaster_types,
    )

    alerts_contract = build_alert_contract(
        dedupe_result.events,
        interval_minutes=config.check_interval_minutes,
    )

    summary = (
        f"Replay complete: items={len(raw_items)}, events={len(dedupe_result.events)}, "
        f"critical_high={len(alerts_contract['critical_high_alerts'])}, "
        f"medium_updates={len(alerts_contract['medium_updates'])}"
    )

    return ReplayResult(
        summary=summary,
        events=dedupe_result.events,
        current_hashes=dedupe_result.current_hashes,
        alerts_contract=alerts_contract,
    )

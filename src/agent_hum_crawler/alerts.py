"""Alert output contract formatting for Moltis chat integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import ProcessedEvent


def build_alert_contract(events: list[ProcessedEvent], interval_minutes: int) -> dict:
    critical_high = [
        _event_payload(e)
        for e in events
        if e.severity in {"critical", "high"}
    ]

    medium_updates = [
        _event_payload(e)
        for e in events
        if e.severity == "medium" and e.status in {"new", "updated"}
    ]

    watchlist_signals = [
        _event_payload(e)
        for e in events
        if e.severity == "low" or (e.severity == "medium" and e.status == "unchanged")
    ]

    source_log = [
        {
            "event_id": e.event_id,
            "connector": e.connector,
            "source_type": e.source_type,
            "url": str(e.url),
            "published_at": e.published_at,
            "corroboration_sources": e.corroboration_sources,
        }
        for e in events
    ]

    next_check_time = (datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)).isoformat()

    return {
        "critical_high_alerts": critical_high,
        "medium_updates": medium_updates,
        "watchlist_signals": watchlist_signals,
        "source_log": source_log,
        "next_check_time": next_check_time,
    }


def _event_payload(event: ProcessedEvent) -> dict:
    return {
        "event_id": event.event_id,
        "status": event.status,
        "severity": event.severity,
        "confidence": event.confidence,
        "llm_enriched": event.llm_enriched,
        "country": event.country,
        "disaster_type": event.disaster_type,
        "title": event.title,
        "summary": event.summary,
        "url": str(event.url),
        "published_at": event.published_at,
        "citations": [c.model_dump(mode="json") for c in event.citations],
        "corroboration": {
            "sources": event.corroboration_sources,
            "connectors": event.corroboration_connectors,
            "source_types": event.corroboration_source_types,
        },
    }

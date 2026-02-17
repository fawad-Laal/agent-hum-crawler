from agent_hum_crawler.alerts import build_alert_contract
from agent_hum_crawler.models import ProcessedEvent


def _event(severity: str, status: str) -> ProcessedEvent:
    return ProcessedEvent(
        event_id=f"{severity}-{status}",
        status=status,
        connector="government_feeds",
        source_type="official",
        url="https://example.com/item",
        title=f"{severity} event",
        country="Pakistan",
        disaster_type="flood",
        published_at="2026-02-17T00:00:00Z",
        severity=severity,
        confidence="high",
        summary="sample",
        corroboration_sources=2,
        corroboration_connectors=2,
        corroboration_source_types=1,
    )


def test_alert_contract_sections() -> None:
    events = [
        _event("critical", "new"),
        _event("high", "updated"),
        _event("medium", "updated"),
        _event("low", "new"),
    ]

    contract = build_alert_contract(events, interval_minutes=30)
    assert len(contract["critical_high_alerts"]) == 2
    assert len(contract["medium_updates"]) == 1
    assert len(contract["watchlist_signals"]) == 1
    assert len(contract["source_log"]) == 4
    assert "next_check_time" in contract

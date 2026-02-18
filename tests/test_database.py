from pathlib import Path

from sqlmodel import Session, select

from agent_hum_crawler.database import (
    EventRecord,
    build_engine,
    build_source_health_report,
    get_recent_cycles,
    init_db,
    persist_cycle,
)
from agent_hum_crawler.models import ProcessedEvent, RawSourceItem


def test_persist_cycle(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)

    raw = [
        RawSourceItem(
            connector="reliefweb",
            source_type="humanitarian",
            url="https://example.org/item1",
            title="Flood warning",
            published_at="2026-02-17",
            country_candidates=["Pakistan"],
            text="Flood warning text",
            language="en",
        )
    ]

    events = [
        ProcessedEvent(
            event_id="abc123",
            status="new",
            connector="reliefweb",
            source_type="humanitarian",
            url="https://example.org/item1",
            title="Flood warning",
            country="Pakistan",
            disaster_type="flood",
            published_at="2026-02-17",
            severity="medium",
            confidence="medium",
            summary="Flood warning text",
            corroboration_sources=2,
            corroboration_connectors=2,
            corroboration_source_types=2,
        )
    ]

    connector_metrics = [
        {
            "connector": "government_feeds",
            "attempted_sources": 2,
            "healthy_sources": 1,
            "failed_sources": 1,
            "fetched_count": 10,
            "matched_count": 1,
            "errors": ["timeout"],
            "source_results": [
                {
                    "source_name": "Gov Feed A",
                    "source_url": "https://example.org/feed-a.xml",
                    "status": "ok",
                    "error": "",
                    "fetched_count": 10,
                    "matched_count": 1,
                },
                {
                    "source_name": "Gov Feed B",
                    "source_url": "https://example.org/feed-b.xml",
                    "status": "failed",
                    "error": "timeout",
                    "fetched_count": 0,
                    "matched_count": 0,
                },
            ],
        }
    ]

    cycle_id = persist_cycle(
        raw_items=raw,
        events=events,
        connector_count=1,
        summary="ok",
        connector_metrics=connector_metrics,
        path=db_path,
    )
    assert cycle_id > 0

    cycles = get_recent_cycles(limit=5, path=db_path)
    assert len(cycles) == 1
    assert cycles[0].event_count == 1

    engine = build_engine(db_path)
    with Session(engine) as session:
        record = session.exec(select(EventRecord)).first()
        assert record is not None
        assert record.corroboration_sources == 2
        assert record.corroboration_connectors == 2
        assert record.corroboration_source_types == 2

    health = build_source_health_report(limit_cycles=5, path=db_path)
    assert health["cycles_analyzed"] == 1
    assert health["connectors"][0]["connector"] == "government_feeds"
    assert health["connectors"][0]["failed_sources"] == 1
    assert len(health["sources"]) == 2

    from agent_hum_crawler.database import build_quality_report

    quality = build_quality_report(limit_cycles=5, path=db_path)
    assert "llm_attempted_events" in quality
    assert "llm_enriched_events" in quality
    assert "citation_coverage_rate" in quality

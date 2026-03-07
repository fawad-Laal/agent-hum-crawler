from pathlib import Path

import pytest
from sqlmodel import Session, select

from agent_hum_crawler.database import (
    EventRecord,
    build_engine,
    build_source_health_report,
    default_db_path,
    get_data_root,
    get_recent_cycles,
    init_db,
    persist_cycle,
    verify_schema_drift,
)
from agent_hum_crawler.models import ProcessedEvent, RawSourceItem


# ── 6B.3: storage-path centralisation ─────────────────────────────────────


def test_get_data_root_default() -> None:
    """Default root is ~/.moltis/agent-hum-crawler when env var is absent."""
    expected = Path.home() / ".moltis" / "agent-hum-crawler"
    assert get_data_root() == expected


def test_get_data_root_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MOLTIS_DATA_ROOT overrides the default root."""
    monkeypatch.setenv("MOLTIS_DATA_ROOT", str(tmp_path))
    assert get_data_root() == tmp_path


def test_default_db_path_uses_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """default_db_path() is data_root / monitoring.db."""
    monkeypatch.setenv("MOLTIS_DATA_ROOT", str(tmp_path))
    assert default_db_path() == tmp_path / "monitoring.db"


# ── 6B.4: schema drift verification ───────────────────────────────────────


def test_verify_schema_drift_no_db(tmp_path: Path) -> None:
    """Returns a single warning when the database file doesn't exist."""
    absent = tmp_path / "nonexistent.db"
    warnings = verify_schema_drift(absent)
    assert len(warnings) == 1
    assert "not found" in warnings[0].lower()


def test_verify_schema_drift_in_sync(tmp_path: Path) -> None:
    """Returns no warnings for a freshly initialised database."""
    db = tmp_path / "monitoring.db"
    init_db(db)
    warnings = verify_schema_drift(db)
    assert warnings == [], f"Unexpected drift warnings: {warnings}"


def test_verify_schema_drift_detects_missing_column(tmp_path: Path) -> None:
    """Reports a missing column when the live table is missing columns vs the model."""
    import sqlite3

    db = tmp_path / "monitoring.db"
    # Build a minimal cyclerun table that is missing most model columns
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE TABLE cyclerun (id INTEGER PRIMARY KEY, run_at TEXT)")
        conn.commit()
    finally:
        conn.close()

    warnings = verify_schema_drift(db)
    cyclerun_warnings = [w for w in warnings if "cyclerun" in w]
    assert cyclerun_warnings, "Expected drift warnings for cyclerun but got none"


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


def test_source_health_recovered_not_counted_as_failed(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)
    persist_cycle(
        raw_items=[],
        events=[],
        connector_count=1,
        summary="ok",
        connector_metrics=[
            {
                "connector": "government_feeds",
                "attempted_sources": 1,
                "healthy_sources": 1,
                "failed_sources": 0,
                "fetched_count": 10,
                "matched_count": 0,
                "errors": [],
                "source_results": [
                    {
                        "source_name": "GDACS",
                        "source_url": "https://www.gdacs.org/xml/rss.xml",
                        "status": "recovered",
                        "error": "encoding recovered",
                        "fetched_count": 10,
                        "matched_count": 0,
                    }
                ],
            }
        ],
        path=db_path,
    )

    health = build_source_health_report(limit_cycles=5, path=db_path)
    assert health["sources"][0]["failed_runs"] == 0
    assert health["sources"][0]["failure_rate"] == 0.0

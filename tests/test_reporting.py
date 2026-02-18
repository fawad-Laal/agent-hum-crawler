from pathlib import Path

from agent_hum_crawler.database import init_db, persist_cycle
from agent_hum_crawler.models import ProcessedEvent, RawSourceItem
from agent_hum_crawler.reporting import build_graph_context, render_long_form_report


def test_graph_context_and_report_render(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)

    raw_items = [
        RawSourceItem(
            connector="government_feeds",
            source_type="official",
            url="https://example.org/madagascar-cyclone-1",
            title="Madagascar cyclone update",
            published_at="2026-02-18T10:00:00Z",
            country_candidates=["Madagascar"],
            text="Cyclone conditions intensified across northern districts. Emergency shelters activated.",
            language="en",
            content_mode="content-level",
        )
    ]
    events = [
        ProcessedEvent(
            event_id="evt-1",
            status="new",
            connector="government_feeds",
            source_type="official",
            url="https://example.org/madagascar-cyclone-1",
            title="Madagascar cyclone update",
            country="Madagascar",
            disaster_type="cyclone/storm",
            published_at="2026-02-18T10:00:00Z",
            severity="high",
            confidence="high",
            summary="Cyclone intensified and shelters activated.",
            corroboration_sources=2,
            corroboration_connectors=1,
            corroboration_source_types=1,
        )
    ]
    persist_cycle(
        raw_items=raw_items,
        events=events,
        connector_count=1,
        summary="cycle summary",
        path=db_path,
    )

    ctx = build_graph_context(
        countries=["Madagascar"],
        disaster_types=["cyclone/storm"],
        limit_cycles=5,
        limit_events=10,
        path=db_path,
    )
    assert int(ctx["meta"]["events_selected"]) >= 1
    md = render_long_form_report(graph_context=ctx, title="Test Report", use_llm=False)
    assert "# Test Report" in md
    assert "Incident Highlights" in md
    assert "https://example.org/madagascar-cyclone-1" in md

from pathlib import Path

from agent_hum_crawler.database import init_db, persist_cycle
from agent_hum_crawler.models import ProcessedEvent, RawSourceItem
from agent_hum_crawler.reporting import (
    build_graph_context,
    evaluate_report_quality,
    render_long_form_report,
    write_report_file,
)


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
    assert "## Citations" in md
    assert "Citation: [1]" in md
    assert "https://example.org/madagascar-cyclone-1" in md
    quality = evaluate_report_quality(report_markdown=md, min_citation_density=0.001)
    assert quality["status"] == "pass"


def test_report_quality_fails_when_sections_missing() -> None:
    bad_md = "# Report\n\n## Executive Summary\nNo links.\n"
    quality = evaluate_report_quality(report_markdown=bad_md, min_citation_density=0.001)
    assert quality["status"] == "fail"
    assert quality["metrics"]["missing_sections"]


def test_write_report_default_path_is_project_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = write_report_file(report_markdown="# Sample\n")
    assert out.parent == tmp_path / "reports"
    assert out.exists()


def test_render_uses_template_section_names(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)
    raw_items = [
        RawSourceItem(
            connector="government_feeds",
            source_type="official",
            url="https://example.org/event",
            title="Sample event",
            published_at="2026-02-18T10:00:00Z",
            country_candidates=["Madagascar"],
            text="Sample long text for event.",
            language="en",
            content_mode="content-level",
        )
    ]
    events = [
        ProcessedEvent(
            event_id="evt-template",
            status="new",
            connector="government_feeds",
            source_type="official",
            url="https://example.org/event",
            title="Sample event",
            country="Madagascar",
            disaster_type="cyclone/storm",
            published_at="2026-02-18T10:00:00Z",
            severity="high",
            confidence="high",
            summary="Sample summary.",
            corroboration_sources=1,
            corroboration_connectors=1,
            corroboration_source_types=1,
        )
    ]
    persist_cycle(raw_items=raw_items, events=events, connector_count=1, summary="ok", path=db_path)
    ctx = build_graph_context(
        countries=["Madagascar"],
        disaster_types=["cyclone/storm"],
        limit_cycles=3,
        limit_events=5,
        path=db_path,
    )
    template_path = tmp_path / "report_template.json"
    template_path.write_text(
        '{'
        '"sections":{"source_reliability":"Source Reliability"},'
        '"limits":{"max_incident_highlights":5}'
        '}',
        encoding="utf-8",
    )
    md = render_long_form_report(graph_context=ctx, use_llm=False, template_path=template_path)
    assert "## Source Reliability" in md

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


def test_strict_filters_prevents_cross_filter_fallback(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)
    raw_items = [
        RawSourceItem(
            connector="government_feeds",
            source_type="official",
            url="https://example.org/event-madagascar",
            title="Sample Madagascar event",
            published_at="2026-02-18T10:00:00Z",
            country_candidates=["Madagascar"],
            text="Sample long text for event.",
            language="en",
            content_mode="content-level",
        )
    ]
    events = [
        ProcessedEvent(
            event_id="evt-strict-1",
            status="new",
            connector="government_feeds",
            source_type="official",
            url="https://example.org/event-madagascar",
            title="Sample Madagascar event",
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

    strict_ctx = build_graph_context(
        countries=["Mozambique"],
        disaster_types=["flood"],
        limit_cycles=3,
        limit_events=5,
        path=db_path,
        strict_filters=True,
    )
    relaxed_ctx = build_graph_context(
        countries=["Mozambique"],
        disaster_types=["flood"],
        limit_cycles=3,
        limit_events=5,
        path=db_path,
        strict_filters=False,
    )
    assert int(strict_ctx["meta"]["events_selected"]) == 0
    assert int(relaxed_ctx["meta"]["events_selected"]) >= 1


def test_graph_context_normalizes_disaster_filter_aliases(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)
    raw_items = [
        RawSourceItem(
            connector="government_feeds",
            source_type="official",
            url="https://example.org/moz-flood",
            title="Mozambique flood event",
            published_at="2026-02-18T10:00:00Z",
            country_candidates=["Mozambique"],
            text="Flood waters displaced thousands in central Mozambique.",
            language="en",
            content_mode="content-level",
        )
    ]
    events = [
        ProcessedEvent(
            event_id="evt-moz-flood-1",
            status="new",
            connector="government_feeds",
            source_type="official",
            url="https://example.org/moz-flood",
            title="Mozambique flood event",
            country="Mozambique",
            disaster_type="flood",
            published_at="2026-02-18T10:00:00Z",
            severity="high",
            confidence="high",
            summary="Flood impact increased in central Mozambique.",
            corroboration_sources=1,
            corroboration_connectors=1,
            corroboration_source_types=1,
        )
    ]
    persist_cycle(raw_items=raw_items, events=events, connector_count=1, summary="ok", path=db_path)
    ctx = build_graph_context(
        countries=["Mozambique"],
        disaster_types=["Floods"],
        limit_cycles=3,
        limit_events=5,
        path=db_path,
        strict_filters=True,
    )
    assert int(ctx["meta"]["events_selected"]) == 1


def test_graph_context_applies_max_age_days_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)
    raw_items = [
        RawSourceItem(
            connector="government_feeds",
            source_type="official",
            url="https://example.org/pk-old-flood",
            title="Pakistan flood historical event",
            published_at="Fri, 05 Dec 2025 12:00:00 +0000",
            country_candidates=["Pakistan"],
            text="Historical flood event in Pakistan.",
            language="en",
            content_mode="content-level",
        )
    ]
    events = [
        ProcessedEvent(
            event_id="evt-pk-old-flood",
            status="new",
            connector="government_feeds",
            source_type="official",
            url="https://example.org/pk-old-flood",
            title="Pakistan flood historical event",
            country="Pakistan",
            disaster_type="flood",
            published_at="Fri, 05 Dec 2025 12:00:00 +0000",
            severity="medium",
            confidence="high",
            summary="Historical flood event in Pakistan.",
            corroboration_sources=1,
            corroboration_connectors=1,
            corroboration_source_types=1,
        )
    ]
    persist_cycle(raw_items=raw_items, events=events, connector_count=1, summary="ok", path=db_path)
    recent_ctx = build_graph_context(
        countries=["Pakistan"],
        disaster_types=["flood"],
        max_age_days=30,
        limit_cycles=3,
        limit_events=5,
        path=db_path,
        strict_filters=True,
    )
    assert int(recent_ctx["meta"]["events_selected"]) == 0


def test_report_quality_fails_on_invalid_citation_ref() -> None:
    bad_md = (
        "# Report\n\n"
        "## Executive Summary\nok\n\n"
        "## Incident Highlights\n"
        "1. **Item**\n"
        "   - Summary: Example.\n"
        "   - Citation: [9]\n\n"
        "## Source and Connector Reliability Snapshot\nok\n\n"
        "## Risk Outlook\nok\n\n"
        "## Method\nok\n\n"
        "## Citations\n"
        "1. https://example.org/a\n"
    )
    quality = evaluate_report_quality(report_markdown=bad_md, min_citation_density=0.001)
    assert quality["status"] == "fail"
    assert quality["metrics"]["invalid_citation_refs"] == [9]


def test_no_evidence_report_passes_quality_gate() -> None:
    md = render_long_form_report(
        graph_context={
            "evidence": [],
            "meta": {
                "cycles_analyzed": 5,
                "events_considered": 100,
                "events_selected": 0,
                "filter_countries": ["mozambique"],
                "filter_disaster_types": ["flood"],
            },
        },
        title="No Evidence Test",
        use_llm=False,
    )
    assert "No evidence found for selected filters and cycles." in md
    quality = evaluate_report_quality(report_markdown=md, min_citation_density=0.005)
    assert quality["status"] == "pass"
    assert quality["metrics"]["no_evidence_mode"] is True


def test_report_quality_allows_single_incident_low_density_when_cited() -> None:
    md = (
        "# Report\n\n"
        "## Executive Summary\n"
        + ("word " * 120)
        + "\n\n"
        "## Incident Highlights\n"
        "1. **Only Incident** (Pakistan | flood | severity=low, confidence=medium)\n"
        "   - Summary: Example summary.\n"
        "   - Citation: [1]\n\n"
        "## Source and Connector Reliability Snapshot\n"
        + ("word " * 120)
        + "\n\n"
        "## Risk Outlook\n"
        + ("word " * 120)
        + "\n\n"
        "## Method\n"
        + ("word " * 80)
        + "\n\n"
        "## Citations\n"
        "1. https://example.org/source\n"
    )
    quality = evaluate_report_quality(report_markdown=md, min_citation_density=0.005)
    assert quality["status"] == "pass"
    assert quality["metrics"]["incident_blocks_detected"] == 1
    assert float(quality["metrics"]["effective_min_citation_density"]) == 0.002


def test_render_uses_canonical_url_for_citations(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)
    raw_items = [
        RawSourceItem(
            connector="local_news_feeds",
            source_type="news",
            url="https://news.google.com/rss/articles/example123?oc=5",
            canonical_url="https://www.reuters.com/world/africa/example-story",
            title="[LocalFeed-1] Reuters story",
            published_at="2026-02-19T10:00:00Z",
            country_candidates=["Madagascar"],
            text="Flood impact expanded in Madagascar.",
            language="en",
            content_mode="link-level",
        )
    ]
    events = [
        ProcessedEvent(
            event_id="evt-canon-1",
            status="new",
            connector="local_news_feeds",
            source_type="news",
            url="https://news.google.com/rss/articles/example123?oc=5",
            canonical_url="https://www.reuters.com/world/africa/example-story",
            title="[LocalFeed-1] Reuters story",
            country="Madagascar",
            disaster_type="flood",
            published_at="2026-02-19T10:00:00Z",
            severity="medium",
            confidence="medium",
            summary="Flood impact expanded in Madagascar.",
            corroboration_sources=1,
            corroboration_connectors=1,
            corroboration_source_types=1,
        )
    ]
    persist_cycle(raw_items=raw_items, events=events, connector_count=1, summary="ok", path=db_path)
    ctx = build_graph_context(
        countries=["Madagascar"],
        disaster_types=["flood"],
        limit_cycles=5,
        limit_events=5,
        path=db_path,
    )
    md = render_long_form_report(graph_context=ctx, title="Canonical Citation Test", use_llm=False)
    assert "https://www.reuters.com/world/africa/example-story" in md
    assert "news.google.com/rss/articles/example123" not in md


def test_graph_context_country_balance_and_caps(tmp_path: Path) -> None:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)
    raw_items = []
    events = []
    for idx in range(4):
        raw_items.append(
            RawSourceItem(
                connector="local_news_feeds",
                source_type="news",
                url=f"https://example.org/mg-{idx}",
                title="[LocalFeed-1] Madagascar flood",
                published_at="2026-02-19T10:00:00Z",
                country_candidates=["Madagascar"],
                text="Madagascar flood severe impact.",
                language="en",
                content_mode="link-level",
            )
        )
        events.append(
            ProcessedEvent(
                event_id=f"evt-mg-{idx}",
                status="new",
                connector="local_news_feeds",
                source_type="news",
                url=f"https://example.org/mg-{idx}",
                title="[LocalFeed-1] Madagascar flood",
                country="Madagascar",
                disaster_type="flood",
                published_at="2026-02-19T10:00:00Z",
                severity="medium",
                confidence="medium",
                summary="Madagascar flood severe impact.",
                corroboration_sources=1,
                corroboration_connectors=1,
                corroboration_source_types=1,
            )
        )
    raw_items.append(
        RawSourceItem(
            connector="un_humanitarian_feeds",
            source_type="humanitarian",
            url="https://news.un.org/feed/view/en/story/2026/02/moz-flood",
            title="[UN News Humanitarian] Mozambique flood update",
            published_at="2026-02-19T10:00:00Z",
            country_candidates=["Mozambique"],
            text="Mozambique flood displaced families.",
            language="en",
            content_mode="link-level",
        )
    )
    events.append(
        ProcessedEvent(
            event_id="evt-mz-1",
            status="new",
            connector="un_humanitarian_feeds",
            source_type="humanitarian",
            url="https://news.un.org/feed/view/en/story/2026/02/moz-flood",
            title="[UN News Humanitarian] Mozambique flood update",
            country="Mozambique",
            disaster_type="flood",
            published_at="2026-02-19T10:00:00Z",
            severity="high",
            confidence="high",
            summary="Mozambique flood displaced families.",
            corroboration_sources=1,
            corroboration_connectors=1,
            corroboration_source_types=1,
        )
    )
    persist_cycle(raw_items=raw_items, events=events, connector_count=2, summary="ok", path=db_path)
    ctx = build_graph_context(
        countries=["Madagascar", "Mozambique"],
        disaster_types=["flood"],
        limit_cycles=5,
        limit_events=4,
        country_min_events=1,
        max_per_connector=3,
        max_per_source=2,
        path=db_path,
        strict_filters=True,
    )
    selected = ctx["evidence"]
    assert any(str(e.get("country", "")).lower() == "mozambique" for e in selected)
    by_connector = {}
    for ev in selected:
        connector = str(ev.get("connector", ""))
        by_connector[connector] = by_connector.get(connector, 0) + 1
    assert max(by_connector.values()) <= 3

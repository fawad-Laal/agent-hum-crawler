from agent_hum_crawler.llm_enrichment import enrich_events_with_llm
from agent_hum_crawler.models import ProcessedEvent, RawSourceItem


def _sample_event() -> ProcessedEvent:
    return ProcessedEvent(
        event_id="e1",
        status="new",
        connector="reliefweb",
        source_type="humanitarian",
        url="https://example.org/report/1",
        title="Cyclone impact update",
        country="Madagascar",
        disaster_type="cyclone/storm",
        published_at="2026-02-18T10:00:00Z",
        severity="high",
        confidence="medium",
        summary="Initial summary",
    )


def _sample_raw_item() -> RawSourceItem:
    return RawSourceItem(
        connector="reliefweb",
        source_type="humanitarian",
        url="https://example.org/report/1",
        title="Cyclone impact update",
        published_at="2026-02-18T10:00:00Z",
        country_candidates=["Madagascar"],
        text=(
            "Heavy rains caused flooding in Toamasina region and more than "
            "12,000 people were displaced according to local responders."
        ),
        language="en",
        content_mode="content-level",
    )


def test_enrichment_success_with_valid_citation() -> None:
    event = _sample_event()
    raw_item = _sample_raw_item()

    def fake_complete(_, __):
        return {
            "summary": "Flooding displaced over 12,000 people in Toamasina.",
            "severity": "high",
            "confidence": "high",
            "citations": [
                {
                    "url": "https://example.org/report/1",
                    "quote": "more than 12,000 people were displaced",
                    "quote_start": 52,
                    "quote_end": 90,
                }
            ],
        }

    enriched, stats = enrich_events_with_llm([event], [raw_item], complete_fn=fake_complete)
    assert stats["enriched_count"] == 1
    assert enriched[0].llm_enriched is True
    assert enriched[0].confidence == "high"
    assert len(enriched[0].citations) == 1


def test_enrichment_recovers_when_indices_wrong_but_quote_valid() -> None:
    event = _sample_event()
    raw_item = _sample_raw_item()

    def fake_complete(_, __):
        return {
            "summary": "Flooding displaced over 12,000 people in Toamasina.",
            "severity": "high",
            "confidence": "high",
            "citations": [
                {
                    "url": "https://example.org/report/1",
                    "quote": "more than 12,000 people were displaced",
                    "quote_start": 0,
                    "quote_end": 10,
                }
            ],
        }

    enriched, stats = enrich_events_with_llm([event], [raw_item], complete_fn=fake_complete)
    assert stats["enriched_count"] == 1
    assert stats["validation_fail_count"] == 0
    assert enriched[0].llm_enriched is True
    citation = enriched[0].citations[0]
    assert citation.quote == "more than 12,000 people were displaced"
    assert citation.quote_start == 52
    assert citation.quote_end == 90


def test_enrichment_recovers_when_quote_not_in_text() -> None:
    event = _sample_event()
    raw_item = _sample_raw_item()

    def fake_complete(_, __):
        return {
            "summary": "Mismatch quote summary",
            "severity": "high",
            "confidence": "high",
            "citations": [
                {
                    "url": "https://example.org/report/1",
                    "quote": "this quote does not exist in source",
                    "quote_start": 0,
                    "quote_end": 12,
                }
            ],
        }

    enriched, stats = enrich_events_with_llm([event], [raw_item], complete_fn=fake_complete)
    assert stats["fallback_count"] == 0
    assert stats["validation_fail_count"] == 0
    assert stats["citation_recovery_count"] == 1
    assert enriched[0].llm_enriched is True
    assert len(enriched[0].citations) == 1


def test_enrichment_fallback_on_invalid_severity() -> None:
    event = _sample_event()
    raw_item = _sample_raw_item()

    def fake_complete(_, __):
        return {
            "summary": "Invalid severity should force fallback",
            "severity": "urgent",
            "confidence": "high",
            "citations": [],
        }

    enriched, stats = enrich_events_with_llm([event], [raw_item], complete_fn=fake_complete)
    assert stats["fallback_count"] == 1
    assert stats["validation_fail_count"] == 1
    assert enriched[0].llm_enriched is False
    assert enriched[0].summary == "Initial summary"

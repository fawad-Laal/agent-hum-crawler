import pytest

from agent_hum_crawler.llm_enrichment import (
    _call_batch_llm,
    enrich_events_batch,
    enrich_events_with_llm,
)
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


# ── Batch enrichment tests ────────────────────────────────────────────


def test_batch_enrichment_disabled_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """enrich_events_batch returns (events unchanged, enabled=False) when no API key."""
    import agent_hum_crawler.llm_enrichment as m

    monkeypatch.setattr(m, "get_openai_api_key", lambda: None)

    event = _sample_event()
    raw_item = _sample_raw_item()
    enriched, stats = enrich_events_batch([event], [raw_item])

    assert stats["enabled"] is False
    assert stats["reason"] == "no_api_key"
    assert len(enriched) == 1
    # Event returned unchanged — not enriched
    assert enriched[0].llm_enriched is False


def test_batch_enrichment_success_via_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """enrich_events_batch applies enriched data when _call_batch_llm succeeds."""
    import agent_hum_crawler.llm_enrichment as m

    monkeypatch.setattr(m, "get_openai_api_key", lambda: "sk-test")
    monkeypatch.setattr(
        m,
        "_call_batch_llm",
        lambda _key, payload: {
            "items": [
                {
                    "index": 0,
                    "summary": "Batch enriched: 12,000 displaced in Toamasina.",
                    "severity": "high",
                    "confidence": "high",
                }
            ]
        },
    )

    event = _sample_event()
    raw_item = _sample_raw_item()
    enriched, stats = enrich_events_batch([event], [raw_item])

    assert stats["enabled"] is True
    assert stats["mode"] == "batch"
    assert stats["enriched_count"] == 1
    assert stats["fallback_count"] == 0
    assert stats["batches_sent"] == 1
    assert enriched[0].llm_enriched is True
    assert enriched[0].summary == "Batch enriched: 12,000 displaced in Toamasina."
    assert enriched[0].severity == "high"
    assert enriched[0].confidence == "high"


def test_batch_enrichment_per_batch_fallback_on_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When _call_batch_llm raises, the whole batch falls back to original events unchanged."""
    import agent_hum_crawler.llm_enrichment as m

    monkeypatch.setattr(m, "get_openai_api_key", lambda: "sk-test")
    monkeypatch.setattr(m, "_call_batch_llm", lambda *_: (_ for _ in ()).throw(RuntimeError("timeout")))

    event = _sample_event()
    raw_item = _sample_raw_item()
    enriched, stats = enrich_events_batch([event], [raw_item])

    assert stats["enabled"] is True
    assert stats["provider_error_count"] == 1
    assert stats["fallback_count"] == 1
    assert stats["enriched_count"] == 0
    # Event returned unchanged — original summary preserved
    assert enriched[0].llm_enriched is False
    assert enriched[0].summary == "Initial summary"

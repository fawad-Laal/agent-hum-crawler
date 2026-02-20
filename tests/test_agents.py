"""Tests for agents abstraction layer (Phase 3 — Task 3.5)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from agent_hum_crawler.agents import (
    Agent,
    AgentResult,
    BatchEnrichmentAgent,
    EnrichmentAgent,
    GazetteerAgent,
    ReportNarrativeAgent,
    SANarrativeAgent,
)
from agent_hum_crawler.llm_provider import LLMProvider


# ── Helpers ──────────────────────────────────────────────────────────


class FakeProvider(LLMProvider):
    """Deterministic LLM provider for testing."""

    def __init__(self, return_value: Any = None, raise_on_call: bool = False):
        self._return_value = return_value
        self._raise_on_call = raise_on_call
        self.call_count = 0

    def name(self) -> str:
        return "fake"

    def complete(self, **kwargs: Any) -> Any:
        self.call_count += 1
        if self._raise_on_call:
            raise RuntimeError("fake error")
        return self._return_value


# ── AgentResult ──────────────────────────────────────────────────────


def test_agent_result_defaults():
    r = AgentResult()
    assert not r.success
    assert r.data is None
    assert r.attempts == 0


# ── EnrichmentAgent ──────────────────────────────────────────────────


def test_enrichment_agent_success():
    provider = FakeProvider(return_value={"summary": "Test summary", "severity": "high"})
    agent = EnrichmentAgent(provider=provider, max_retries=1)
    result = agent.execute(
        system="test", user="test",
        json_schema={"type": "object"}, schema_name="test",
    )
    assert result.success
    assert result.data["summary"] == "Test summary"
    assert result.attempts == 1


def test_enrichment_agent_failure_with_retry():
    provider = FakeProvider(return_value=None)
    agent = EnrichmentAgent(provider=provider, max_retries=3, retry_delay=0.01)
    result = agent.execute(system="test", user="test")
    assert not result.success
    assert result.attempts == 3
    assert result.data is None
    assert result.fallback_data is None  # EnrichmentAgent fallback is None


def test_enrichment_agent_exception_retry():
    provider = FakeProvider(raise_on_call=True)
    agent = EnrichmentAgent(provider=provider, max_retries=2, retry_delay=0.01)
    result = agent.execute(system="test", user="test")
    assert not result.success
    assert provider.call_count == 2
    assert "RuntimeError" in (result.error or "")


def test_enrichment_agent_validation_failure():
    # Returns a dict without 'summary' → fails validation
    provider = FakeProvider(return_value={"no_summary": True})
    agent = EnrichmentAgent(provider=provider, max_retries=2, retry_delay=0.01)
    result = agent.execute(system="test", user="test")
    assert not result.success
    assert result.error == "validate() returned False"


# ── SANarrativeAgent ─────────────────────────────────────────────────


def test_sa_narrative_agent_success():
    provider = FakeProvider(return_value={
        "executive_summary": "The cyclone caused widespread damage across five provinces."
    })
    agent = SANarrativeAgent(provider=provider, max_retries=1)
    result = agent.execute(system="test", user="test")
    assert result.success
    assert "cyclone" in result.data["executive_summary"]


def test_sa_narrative_agent_fallback():
    provider = FakeProvider(return_value=None)
    agent = SANarrativeAgent(provider=provider, max_retries=1, retry_delay=0.01)
    result = agent.execute(system="test", user="test")
    assert not result.success
    assert result.fallback_data == {}


# ── GazetteerAgent ───────────────────────────────────────────────────


def test_gazetteer_agent_success():
    provider = FakeProvider(return_value={
        "admin1": {
            "Maputo": ["Maputo City", "Matola"],
            "Gaza": ["Xai-Xai", "Chokwe"],
            "Inhambane": ["Inhambane City"],
        }
    })
    agent = GazetteerAgent(provider=provider, max_retries=1)
    result = agent.execute(system="test", user="test")
    assert result.success
    assert "Maputo" in result.data


def test_gazetteer_agent_too_few_regions():
    provider = FakeProvider(return_value={
        "admin1": {"OnlyOne": ["Dist"]}
    })
    agent = GazetteerAgent(provider=provider, max_retries=1, retry_delay=0.01)
    result = agent.execute(system="test", user="test")
    assert not result.success  # fails validation (< 3 admin1 regions)


# ── BatchEnrichmentAgent ─────────────────────────────────────────────


def test_batch_enrichment_agent_success():
    provider = FakeProvider(return_value={
        "items": [
            {"index": 0, "summary": "Item 0", "severity": "low", "confidence": "high"},
            {"index": 1, "summary": "Item 1", "severity": "medium", "confidence": "medium"},
        ]
    })
    agent = BatchEnrichmentAgent(provider=provider, max_retries=1)
    result = agent.execute(system="test", user="test")
    assert result.success
    assert len(result.data["items"]) == 2


def test_batch_enrichment_agent_empty_items():
    provider = FakeProvider(return_value={"items": []})
    agent = BatchEnrichmentAgent(provider=provider, max_retries=1, retry_delay=0.01)
    result = agent.execute(system="test", user="test")
    assert not result.success
    assert result.fallback_data == {"items": []}


# ── ReportNarrativeAgent ─────────────────────────────────────────────


def test_report_narrative_agent_success():
    provider = FakeProvider(return_value={
        "executive_summary": "A major flood event.",
        "risk_outlook": "Continued risk of flooding.",
    })
    agent = ReportNarrativeAgent(provider=provider, max_retries=1)
    result = agent.execute(system="test", user="test")
    assert result.success
    assert "flood" in result.data["executive_summary"]

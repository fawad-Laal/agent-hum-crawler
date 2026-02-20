"""Tests for llm_provider module (Phase 3 — Task 3.6)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent_hum_crawler.llm_provider import (
    LLMProvider,
    OpenAIResponsesProvider,
    get_provider,
    register_provider,
)


# ── Provider singleton / registry ────────────────────────────────────


def test_get_provider_returns_openai_default():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        p = get_provider(reset=True)
        assert isinstance(p, OpenAIResponsesProvider)
        assert "openai" in p.name()


def test_get_provider_singleton():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        p1 = get_provider(reset=True)
        p2 = get_provider()
        assert p1 is p2


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_provider(provider_name="nonexistent_provider", reset=True)


def test_register_custom_provider():
    class DummyProvider(LLMProvider):
        def name(self) -> str:
            return "dummy"

        def complete(self, **kwargs: Any) -> None:
            return None

    register_provider("dummy", DummyProvider)
    p = get_provider(provider_name="dummy", reset=True)
    assert p.name() == "dummy"


# ── OpenAIResponsesProvider ──────────────────────────────────────────


def test_openai_provider_no_key_returns_none():
    provider = OpenAIResponsesProvider(api_key="", model="test-model")
    result = provider.complete(system="hello", user="world")
    assert result is None


def test_openai_provider_extract_text():
    data_output_text = {"output_text": "hello world"}
    assert OpenAIResponsesProvider._extract_text(data_output_text) == "hello world"

    data_blocks = {
        "output": [
            {
                "content": [
                    {"text": "  block text  "}
                ]
            }
        ]
    }
    assert OpenAIResponsesProvider._extract_text(data_blocks) == "block text"

    assert OpenAIResponsesProvider._extract_text({}) == ""


def test_openai_provider_json_fallback():
    assert OpenAIResponsesProvider._extract_json_fallback('{"a": 1}') == {"a": 1}
    assert OpenAIResponsesProvider._extract_json_fallback("some text {\"b\": 2} more") == {"b": 2}
    assert OpenAIResponsesProvider._extract_json_fallback("no json here") is None


def test_openai_provider_complete_json():
    """Test structured JSON completion flow."""
    import httpx as _httpx

    mock_response = MagicMock()
    mock_response.json.return_value = {"output_text": json.dumps({"result": "ok"})}
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    provider = OpenAIResponsesProvider(api_key="test-key", model="gpt-test")
    with patch.object(_httpx, "Client", return_value=mock_client):
        result = provider.complete(
            system="test",
            user="test",
            json_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            schema_name="test_schema",
        )
    assert result == {"result": "ok"}


def test_openai_provider_complete_freeform():
    """Test free-form text completion flow."""
    import httpx as _httpx

    mock_response = MagicMock()
    mock_response.json.return_value = {"output_text": "Hello world"}
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    provider = OpenAIResponsesProvider(api_key="test-key", model="gpt-test")
    with patch.object(_httpx, "Client", return_value=mock_client):
        result = provider.complete(system="test", user="test")
    assert result == "Hello world"

"""LLM provider abstraction layer.

Provides a unified interface for LLM completions, decoupling all
application code from a specific vendor SDK or HTTP endpoint.

Providers
---------
- **OpenAIResponsesProvider** — current default (OpenAI ``/v1/responses`` API)

Selection is driven by the ``LLM_PROVIDER`` environment variable
(default ``"openai_responses"``).  At start-up, ``get_provider()``
returns a singleton that every LLM call-site should use.

Usage
-----
::

    from .llm_provider import get_provider

    provider = get_provider()
    result = provider.complete(
        system="You are a helpful assistant.",
        user="Summarise this text.",
        json_schema={"type": "object", ...},
        schema_name="summary",
        timeout=30.0,
    )
    # result is a dict (parsed JSON) or None on failure

"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

_log = logging.getLogger(__name__)

# ── Base class ───────────────────────────────────────────────────────


class LLMProvider(ABC):
    """Abstract base for LLM completions."""

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
        timeout: float = 45.0,
        model: str | None = None,
    ) -> dict[str, Any] | str | None:
        """Run an LLM completion and return parsed output.

        Parameters
        ----------
        system:
            System-role instructions.
        user:
            User-role prompt text (may include JSON payloads).
        json_schema:
            If provided, request structured JSON output compliant
            with this schema.  When ``None`` the provider returns
            free-form text.
        schema_name:
            Identifier for the JSON schema (used by Responses API).
        timeout:
            HTTP timeout in seconds.
        model:
            Override the default model for this call.

        Returns
        -------
        - ``dict`` when *json_schema* is set and parsing succeeds.
        - ``str`` for free-form text completions.
        - ``None`` on failure.
        """

    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""


# ── OpenAI Responses API provider ────────────────────────────────────


class OpenAIResponsesProvider(LLMProvider):
    """Provider backed by OpenAI ``/v1/responses``."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com",
    ) -> None:
        from .settings import get_openai_api_key, get_openai_model

        self._api_key = api_key or get_openai_api_key()
        self._model = model or get_openai_model()
        self._base_url = base_url.rstrip("/")
        self._endpoint = f"{self._base_url}/v1/responses"

    def name(self) -> str:
        return f"openai_responses ({self._model})"

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "response",
        timeout: float = 45.0,
        model: str | None = None,
    ) -> dict[str, Any] | str | None:
        import httpx

        if not self._api_key:
            _log.warning("No OpenAI API key configured — skipping LLM call")
            return None

        effective_model = model or self._model
        body: dict[str, Any] = {
            "model": effective_model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {"role": "user", "content": [{"type": "input_text", "text": user}]},
            ],
        }

        if json_schema is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": json_schema,
                    "strict": True,
                }
            }

        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(
                    self._endpoint,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            _log.warning("LLM call failed: %s", exc)
            return None

        text = self._extract_text(data)
        if not text:
            return None

        if json_schema is not None:
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                # Attempt fallback extraction
                return self._extract_json_fallback(text)

        return text

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        """Extract text content from Responses API output."""
        # Direct output_text field (newer API versions)
        if data.get("output_text"):
            return str(data["output_text"])

        # Walk output blocks
        for block in data.get("output", []) or []:
            for content in block.get("content", []) or []:
                t = content.get("text")
                if isinstance(t, str) and t.strip():
                    return t.strip()
        return ""

    @staticmethod
    def _extract_json_fallback(text: str) -> dict[str, Any] | None:
        """Try to extract a JSON object from possibly messy text."""
        import re

        # Find first { ... } block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except (json.JSONDecodeError, TypeError):
                pass
        return None


# ── Provider registry ────────────────────────────────────────────────

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai_responses": OpenAIResponsesProvider,
}

_provider_instance: LLMProvider | None = None


def get_provider(
    *,
    provider_name: str | None = None,
    reset: bool = False,
    **kwargs: Any,
) -> LLMProvider:
    """Return the configured LLM provider singleton.

    Parameters
    ----------
    provider_name:
        Override environment-based selection.  One of the keys in
        ``_PROVIDERS`` (currently ``"openai_responses"``).
    reset:
        Force re-creation of the singleton (useful for tests).
    **kwargs:
        Passed to the provider constructor.
    """
    global _provider_instance

    if _provider_instance is not None and not reset:
        return _provider_instance

    name = provider_name or os.environ.get("LLM_PROVIDER", "openai_responses")
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown LLM provider {name!r}. "
            f"Available: {', '.join(sorted(_PROVIDERS))}"
        )

    _provider_instance = cls(**kwargs)
    _log.info("LLM provider initialised: %s", _provider_instance.name())
    return _provider_instance


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    """Register a custom LLM provider class.

    Allows extensions to plug in alternative backends without
    modifying this module.
    """
    _PROVIDERS[name] = cls
    _log.info("Registered LLM provider: %s → %s", name, cls.__name__)

"""Agent abstraction layer for LLM-powered tasks.

Provides a common ``Agent`` base class with retry, validation, and
fallback logic.  Concrete agents encapsulate specific LLM workflows
(enrichment, SA narrative generation, gazetteer generation, etc.)
behind a uniform interface.

Concepts
--------
- **Agent**: A reusable, stateless wrapper around an LLM task.
  Each agent has ``run()`` → ``validate()`` → ``fallback()`` lifecycle.
- **AgentResult**: Typed result container with success/failure, data,
  and diagnostics metadata.
- All agents use the ``LLMProvider`` abstraction for vendor-agnostic
  LLM access.

Usage
-----
::

    from .agents import EnrichmentAgent

    agent = EnrichmentAgent()
    result = agent.run(system="...", user="...", schema={...})
    if result.success:
        data = result.data
    else:
        data = result.fallback_data

"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from .llm_provider import LLMProvider, get_provider

_log = logging.getLogger(__name__)

T = TypeVar("T")


# ── Result container ─────────────────────────────────────────────────


@dataclass
class AgentResult(Generic[T]):
    """Result from an agent invocation."""

    success: bool = False
    data: T | None = None
    fallback_data: T | None = None
    error: str | None = None
    attempts: int = 0
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Base Agent ───────────────────────────────────────────────────────


class Agent(ABC, Generic[T]):
    """Abstract base for LLM-powered agents.

    Lifecycle::

        result = agent.execute(...)
        # internally calls: run() → validate() → fallback() if needed

    Subclasses implement:
    - ``run()``       — perform the LLM call
    - ``validate()``  — check the raw output
    - ``fallback()``  — produce a safe default on failure
    """

    def __init__(
        self,
        *,
        provider: LLMProvider | None = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        agent_name: str = "",
    ) -> None:
        self._provider = provider or get_provider()
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._agent_name = agent_name or self.__class__.__name__

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @abstractmethod
    def run(self, **kwargs: Any) -> T | None:
        """Execute the core LLM task.  Return raw output or ``None``."""

    @abstractmethod
    def validate(self, output: T) -> bool:
        """Return True if *output* passes quality checks."""

    @abstractmethod
    def fallback(self, **kwargs: Any) -> T | None:
        """Return a safe fallback value when ``run()`` fails."""

    def execute(self, **kwargs: Any) -> AgentResult[T]:
        """Full lifecycle: run → validate → retry → fallback.

        Returns an :class:`AgentResult` with diagnostics.
        """
        start = time.monotonic()
        last_error: str | None = None
        attempts = 0

        for attempt in range(1, self._max_retries + 1):
            attempts = attempt
            try:
                output = self.run(**kwargs)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                _log.warning(
                    "[%s] attempt %d/%d failed: %s",
                    self._agent_name, attempt, self._max_retries, last_error,
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)
                continue

            if output is None:
                last_error = "run() returned None"
                _log.info(
                    "[%s] attempt %d/%d returned None",
                    self._agent_name, attempt, self._max_retries,
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)
                continue

            if self.validate(output):
                elapsed = (time.monotonic() - start) * 1000
                _log.info(
                    "[%s] succeeded on attempt %d (%.0fms)",
                    self._agent_name, attempt, elapsed,
                )
                return AgentResult(
                    success=True,
                    data=output,
                    attempts=attempts,
                    elapsed_ms=round(elapsed, 1),
                )
            else:
                last_error = "validate() returned False"
                _log.warning(
                    "[%s] attempt %d/%d failed validation",
                    self._agent_name, attempt, self._max_retries,
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * attempt)

        # All attempts exhausted — trigger fallback
        elapsed = (time.monotonic() - start) * 1000
        fb = self.fallback(**kwargs)
        _log.info(
            "[%s] exhausted %d attempts (%.0fms) — using fallback",
            self._agent_name, attempts, elapsed,
        )
        return AgentResult(
            success=False,
            data=None,
            fallback_data=fb,
            error=last_error,
            attempts=attempts,
            elapsed_ms=round(elapsed, 1),
        )


# ── Concrete agents ──────────────────────────────────────────────────


class EnrichmentAgent(Agent[dict]):
    """Agent for single-event LLM enrichment.

    Wraps the LLM call that produces summary + severity + confidence
    for a single humanitarian event.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="EnrichmentAgent", **kwargs)

    def run(
        self,
        *,
        system: str = "",
        user: str = "",
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "event_enrichment",
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> dict | None:
        result = self.provider.complete(
            system=system,
            user=user,
            json_schema=json_schema,
            schema_name=schema_name,
            timeout=timeout,
        )
        if isinstance(result, dict):
            return result
        return None

    def validate(self, output: dict) -> bool:
        if not isinstance(output, dict):
            return False
        # Must have at least a summary
        return bool(output.get("summary"))

    def fallback(self, **kwargs: Any) -> dict | None:
        return None


class SANarrativeAgent(Agent[dict]):
    """Agent for SA narrative section generation.

    Wraps the LLM call that produces narrative text for SA sections
    (executive_summary, national_impact, sector-level analyses, etc.).
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="SANarrativeAgent", **kwargs)

    def run(
        self,
        *,
        system: str = "",
        user: str = "",
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "sa_narrative",
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> dict | None:
        result = self.provider.complete(
            system=system,
            user=user,
            json_schema=json_schema,
            schema_name=schema_name,
            timeout=timeout,
        )
        if isinstance(result, dict):
            return result
        return None

    def validate(self, output: dict) -> bool:
        if not isinstance(output, dict):
            return False
        # At least one non-empty narrative string
        return any(
            isinstance(v, str) and len(v.strip()) > 20
            for v in output.values()
        )

    def fallback(self, **kwargs: Any) -> dict | None:
        return {}


class GazetteerAgent(Agent[dict]):
    """Agent for LLM-driven gazetteer generation.

    Generates admin boundary data (admin1 → admin2 mapping) for a
    country when no static gazetteer file is available.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="GazetteerAgent", **kwargs)

    def run(
        self,
        *,
        system: str = "",
        user: str = "",
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "country_gazetteer",
        timeout: float = 45.0,
        **kwargs: Any,
    ) -> dict | None:
        result = self.provider.complete(
            system=system,
            user=user,
            json_schema=json_schema,
            schema_name=schema_name,
            timeout=timeout,
        )
        if isinstance(result, dict):
            admin1 = result.get("admin1", result)
            if isinstance(admin1, dict) and admin1:
                return admin1
        return None

    def validate(self, output: dict) -> bool:
        if not isinstance(output, dict):
            return False
        # Must have at least 3 admin1 regions
        return len(output) >= 3

    def fallback(self, **kwargs: Any) -> dict | None:
        return None


class BatchEnrichmentAgent(Agent[dict]):
    """Agent for batch event enrichment.

    Processes multiple events in a single LLM call for efficiency.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="BatchEnrichmentAgent", **kwargs)

    def run(
        self,
        *,
        system: str = "",
        user: str = "",
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "batch_enrichment",
        timeout: float = 45.0,
        **kwargs: Any,
    ) -> dict | None:
        result = self.provider.complete(
            system=system,
            user=user,
            json_schema=json_schema,
            schema_name=schema_name,
            timeout=timeout,
        )
        if isinstance(result, dict):
            return result
        return None

    def validate(self, output: dict) -> bool:
        if not isinstance(output, dict):
            return False
        items = output.get("items", [])
        return isinstance(items, list) and len(items) > 0

    def fallback(self, **kwargs: Any) -> dict | None:
        return {"items": []}


class ReportNarrativeAgent(Agent[dict]):
    """Agent for long-form report narrative generation.

    Produces structured report sections (executive summary, incident
    highlights, risk outlook, etc.) from graph evidence.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(agent_name="ReportNarrativeAgent", **kwargs)

    def run(
        self,
        *,
        system: str = "",
        user: str = "",
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "report_narrative",
        timeout: float = 40.0,
        **kwargs: Any,
    ) -> dict | None:
        result = self.provider.complete(
            system=system,
            user=user,
            json_schema=json_schema,
            schema_name=schema_name,
            timeout=timeout,
        )
        if isinstance(result, dict):
            return result
        return None

    def validate(self, output: dict) -> bool:
        if not isinstance(output, dict):
            return False
        return any(isinstance(v, str) and v.strip() for v in output.values())

    def fallback(self, **kwargs: Any) -> dict | None:
        return None

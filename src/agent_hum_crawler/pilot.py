"""Pilot runner to execute multiple cycles and produce sign-off evidence."""

from __future__ import annotations

import time
from typing import Callable

from .config import RuntimeConfig
from .cycle import CycleResult, run_cycle_once
from .database import build_quality_report, build_source_health_report
from .hardening import evaluate_hardening_gate


def run_pilot(
    *,
    config: RuntimeConfig,
    cycles: int,
    limit: int,
    include_content: bool,
    sleep_seconds: float = 0.0,
    max_duplicate_rate: float = 0.10,
    min_traceable_rate: float = 0.95,
    max_connector_failure_rate: float = 0.60,
    min_llm_enrichment_rate: float = 0.10,
    min_citation_coverage_rate: float = 0.95,
    enforce_llm_quality: bool = False,
    run_cycle_fn: Callable[[RuntimeConfig, int, bool], CycleResult] = run_cycle_once,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict:
    cycle_summaries: list[dict] = []
    for idx in range(cycles):
        result = run_cycle_fn(config, limit, include_content)
        cycle_summaries.append(
            {
                "cycle_number": idx + 1,
                "cycle_id": result.cycle_id,
                "summary": result.summary,
                "raw_item_count": result.raw_item_count,
                "event_count": result.event_count,
                "llm_enrichment": result.llm_enrichment,
            }
        )
        if sleep_seconds > 0 and idx < (cycles - 1):
            sleep_fn(sleep_seconds)

    quality = build_quality_report(limit_cycles=cycles)
    source_health = build_source_health_report(limit_cycles=cycles)
    gate = evaluate_hardening_gate(
        quality,
        source_health,
        max_duplicate_rate=max_duplicate_rate,
        min_traceable_rate=min_traceable_rate,
        max_connector_failure_rate=max_connector_failure_rate,
        min_llm_enrichment_rate=min_llm_enrichment_rate,
        min_citation_coverage_rate=min_citation_coverage_rate,
        enforce_llm_quality=enforce_llm_quality,
    )

    return {
        "cycles_requested": cycles,
        "cycles_completed": len(cycle_summaries),
        "cycle_runs": cycle_summaries,
        "quality_report": quality,
        "source_health": source_health,
        "hardening_gate": gate,
    }

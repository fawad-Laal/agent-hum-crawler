"""Hardening gate checks based on quality and source-health reports."""

from __future__ import annotations


def evaluate_hardening_gate(
    quality_report: dict,
    source_health_report: dict,
    *,
    max_duplicate_rate: float = 0.10,
    min_traceable_rate: float = 0.95,
    max_connector_failure_rate: float = 0.60,
    min_llm_enrichment_rate: float = 0.10,
    min_citation_coverage_rate: float = 0.95,
    enforce_llm_quality: bool = False,
) -> dict:
    events_analyzed = int(quality_report.get("events_analyzed", 0))
    cycles_analyzed = int(quality_report.get("cycles_analyzed", 0))

    if cycles_analyzed == 0:
        return {
            "status": "insufficient_data",
            "reason": "No cycles available for hardening gate evaluation.",
            "checks": {},
        }

    duplicate_rate = float(quality_report.get("duplicate_rate_estimate", 0.0))
    traceable_rate = float(quality_report.get("traceable_rate", 0.0))
    llm_attempted_events = int(quality_report.get("llm_attempted_events", 0))
    llm_enrichment_rate = float(quality_report.get("llm_enrichment_rate", 0.0))
    citation_coverage_rate = float(quality_report.get("citation_coverage_rate", 0.0))
    llm_quality_applicable = bool(enforce_llm_quality or llm_attempted_events > 0)

    connectors = source_health_report.get("connectors", []) or []
    worst_connector_failure = max((float(c.get("failure_rate", 0.0)) for c in connectors), default=0.0)

    checks = {
        "duplicate_rate_ok": duplicate_rate <= max_duplicate_rate,
        "traceable_rate_ok": traceable_rate >= min_traceable_rate,
        "connector_failure_ok": worst_connector_failure <= max_connector_failure_rate,
        "llm_enrichment_rate_ok": (
            llm_enrichment_rate >= min_llm_enrichment_rate
            if llm_quality_applicable
            else True
        ),
        "citation_coverage_ok": (
            citation_coverage_rate >= min_citation_coverage_rate
            if llm_quality_applicable
            else True
        ),
    }

    if events_analyzed == 0:
        status = "warning"
        reason = "No events analyzed yet; gate is provisional."
    elif all(checks.values()):
        status = "pass"
        reason = "All hardening thresholds satisfied."
    else:
        status = "fail"
        reason = "One or more hardening thresholds failed."

    return {
        "status": status,
        "reason": reason,
        "checks": checks,
        "metrics": {
            "duplicate_rate": duplicate_rate,
            "traceable_rate": traceable_rate,
            "worst_connector_failure_rate": worst_connector_failure,
            "events_analyzed": events_analyzed,
            "cycles_analyzed": cycles_analyzed,
            "llm_quality_applicable": llm_quality_applicable,
            "llm_attempted_events": llm_attempted_events,
            "llm_enrichment_rate": llm_enrichment_rate,
            "citation_coverage_rate": citation_coverage_rate,
        },
        "thresholds": {
            "max_duplicate_rate": max_duplicate_rate,
            "min_traceable_rate": min_traceable_rate,
            "max_connector_failure_rate": max_connector_failure_rate,
            "min_llm_enrichment_rate": min_llm_enrichment_rate,
            "min_citation_coverage_rate": min_citation_coverage_rate,
            "enforce_llm_quality": enforce_llm_quality,
        },
    }


def evaluate_llm_quality_gate(
    quality_report: dict,
    *,
    min_llm_enrichment_rate: float = 0.10,
    min_citation_coverage_rate: float = 0.95,
    enforce_llm_quality: bool = False,
) -> dict:
    attempted = int(quality_report.get("llm_attempted_events", 0))
    enrichment_rate = float(quality_report.get("llm_enrichment_rate", 0.0))
    citation_rate = float(quality_report.get("citation_coverage_rate", 0.0))
    provider_errors = int(quality_report.get("llm_provider_error_count", 0))
    validation_failures = int(quality_report.get("llm_validation_fail_count", 0))
    applicable = bool(enforce_llm_quality or attempted > 0)

    if not applicable:
        return {
            "status": "warning",
            "reason": "No LLM attempts in analyzed window; LLM quality gate not applicable.",
            "checks": {
                "llm_enrichment_rate_ok": True,
                "citation_coverage_ok": True,
            },
            "metrics": {
                "llm_attempted_events": attempted,
                "llm_enrichment_rate": enrichment_rate,
                "citation_coverage_rate": citation_rate,
                "llm_provider_error_count": provider_errors,
                "llm_validation_fail_count": validation_failures,
            },
            "thresholds": {
                "min_llm_enrichment_rate": min_llm_enrichment_rate,
                "min_citation_coverage_rate": min_citation_coverage_rate,
                "enforce_llm_quality": enforce_llm_quality,
            },
        }

    checks = {
        "llm_enrichment_rate_ok": enrichment_rate >= min_llm_enrichment_rate,
        "citation_coverage_ok": citation_rate >= min_citation_coverage_rate,
    }
    status = "pass" if all(checks.values()) else "fail"
    reason = (
        "LLM quality thresholds satisfied."
        if status == "pass"
        else "One or more LLM quality thresholds failed."
    )
    return {
        "status": status,
        "reason": reason,
        "checks": checks,
        "metrics": {
            "llm_attempted_events": attempted,
            "llm_enrichment_rate": enrichment_rate,
            "citation_coverage_rate": citation_rate,
            "llm_provider_error_count": provider_errors,
            "llm_validation_fail_count": validation_failures,
        },
        "thresholds": {
            "min_llm_enrichment_rate": min_llm_enrichment_rate,
            "min_citation_coverage_rate": min_citation_coverage_rate,
            "enforce_llm_quality": enforce_llm_quality,
        },
    }

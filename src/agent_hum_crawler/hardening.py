"""Hardening gate checks based on quality and source-health reports."""

from __future__ import annotations


def evaluate_hardening_gate(
    quality_report: dict,
    source_health_report: dict,
    *,
    max_duplicate_rate: float = 0.10,
    min_traceable_rate: float = 0.95,
    max_connector_failure_rate: float = 0.60,
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

    connectors = source_health_report.get("connectors", []) or []
    worst_connector_failure = max((float(c.get("failure_rate", 0.0)) for c in connectors), default=0.0)

    checks = {
        "duplicate_rate_ok": duplicate_rate <= max_duplicate_rate,
        "traceable_rate_ok": traceable_rate >= min_traceable_rate,
        "connector_failure_ok": worst_connector_failure <= max_connector_failure_rate,
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
        },
        "thresholds": {
            "max_duplicate_rate": max_duplicate_rate,
            "min_traceable_rate": min_traceable_rate,
            "max_connector_failure_rate": max_connector_failure_rate,
        },
    }

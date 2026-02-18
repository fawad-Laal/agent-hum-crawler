"""Moltis conformance evaluation utilities."""

from __future__ import annotations


def evaluate_moltis_conformance(
    *,
    hardening_status: str,
    checks: dict[str, str],
) -> dict:
    normalized = {}
    for name, value in checks.items():
        v = (value or "pending").strip().lower()
        normalized[name] = v if v in {"pass", "fail", "pending"} else "pending"

    failed = sorted(name for name, value in normalized.items() if value == "fail")
    pending = sorted(name for name, value in normalized.items() if value == "pending")
    passed = sorted(name for name, value in normalized.items() if value == "pass")

    if failed:
        status = "fail"
        reason = "One or more Moltis conformance checks failed."
    elif hardening_status != "pass":
        status = "warning"
        reason = "Hardening gate is not pass yet; conformance remains provisional."
    elif pending:
        status = "warning"
        reason = "Conformance checks are incomplete."
    else:
        status = "pass"
        reason = "Moltis conformance and hardening checks passed."

    return {
        "status": status,
        "reason": reason,
        "checks": normalized,
        "summary": {
            "passed": passed,
            "failed": failed,
            "pending": pending,
        },
    }

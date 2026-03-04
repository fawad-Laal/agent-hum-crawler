"""GET /api/overview — aggregated dashboard data.

Runs four CLI-equivalent direct calls in parallel threads and returns
the combined payload.  Keeps the same response shape as the legacy
``dashboard_api.py`` so the frontend needs no changes.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from agent_hum_crawler.source_credibility import tier_label

router = APIRouter()

_ROOT = Path(__file__).resolve().parents[5]
_REPORTS_DIR = _ROOT / "reports"


# ── helpers ───────────────────────────────────────────────────────────────


def _quality_report(limit: int = 10) -> dict:
    try:
        from agent_hum_crawler.database import build_quality_report
        return build_quality_report(limit_cycles=limit)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _source_health_report(limit: int = 10) -> dict:
    try:
        from agent_hum_crawler.database import build_source_health_report
        return build_source_health_report(limit_cycles=limit)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _hardening_gate(limit: int = 10) -> dict:
    try:
        from agent_hum_crawler.database import build_quality_report, build_source_health_report
        from agent_hum_crawler.hardening import evaluate_hardening_gate
        q = build_quality_report(limit_cycles=limit)
        sh = build_source_health_report(limit_cycles=limit)
        return evaluate_hardening_gate(q, sh)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _recent_cycles(limit: int = 20) -> list[dict]:
    try:
        from agent_hum_crawler.database import get_recent_cycles
        return [c.model_dump() for c in get_recent_cycles(limit=limit)]
    except Exception:
        return []


def _quality_trend(window: int = 10) -> list[dict]:
    out: list[dict] = []
    for i in range(1, max(window, 1) + 1):
        q = _quality_report(limit=i)
        if not isinstance(q, dict) or "duplicate_rate_estimate" not in q:
            continue
        out.append({
            "limit": i,
            "duplicate_rate_estimate": q.get("duplicate_rate_estimate", 0.0),
            "traceable_rate": q.get("traceable_rate", 0.0),
            "llm_enrichment_rate": q.get("llm_enrichment_rate", 0.0),
            "citation_coverage_rate": q.get("citation_coverage_rate", 0.0),
            "events_analyzed": q.get("events_analyzed", 0),
        })
    return out


def _latest_e2e_summary() -> dict:
    e2e_dir = _ROOT / "artifacts" / "e2e"
    if not e2e_dir.exists():
        return {}
    candidates = sorted([p for p in e2e_dir.iterdir() if p.is_dir()], reverse=True)
    for d in candidates:
        summary_file = d / "summary.json"
        if summary_file.exists():
            try:
                import json
                payload = json.loads(summary_file.read_text(encoding="utf-8"))
                payload["artifact_dir"] = str(d)
                return payload
            except Exception:
                continue
    return {}


def _credibility_distribution() -> dict:
    candidates = sorted(_REPORTS_DIR.glob("report-*.md"), reverse=True)
    for f in candidates[:5]:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        dist: dict[str, int] = {}
        for tier_num in range(1, 5):
            label = tier_label(tier_num)
            m = re.search(rf"\b{re.escape(label)}\b.*?(\d+)", text, re.IGNORECASE)
            if m:
                dist[f"tier_{tier_num}"] = int(m.group(1))
        if dist:
            return {"source": f.name, **dist}
    return {}


# ── route ─────────────────────────────────────────────────────────────────


@router.get("/overview")
def overview() -> dict:
    from agent_hum_crawler.feature_flags import load_feature_flags

    tasks: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_quality_report, 10): "quality",
            pool.submit(_source_health_report, 10): "source_health",
            pool.submit(_hardening_gate, 10): "hardening",
            pool.submit(_recent_cycles, 20): "cycles",
            pool.submit(_quality_trend, 10): "quality_trend",
            pool.submit(_latest_e2e_summary): "e2e",
            pool.submit(_credibility_distribution): "credibility",
        }
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                tasks[key] = fut.result()
            except Exception as exc:
                tasks[key] = {"status": "error", "error": str(exc)}

    return {
        "quality": tasks.get("quality", {}),
        "source_health": tasks.get("source_health", {}),
        "hardening": tasks.get("hardening", {}),
        "cycles": tasks.get("cycles") if isinstance(tasks.get("cycles"), list) else [],
        "quality_trend": tasks.get("quality_trend", []),
        "latest_e2e_summary": tasks.get("e2e", {}),
        "feature_flags": load_feature_flags(),
        "credibility_distribution": tasks.get("credibility", {}),
    }

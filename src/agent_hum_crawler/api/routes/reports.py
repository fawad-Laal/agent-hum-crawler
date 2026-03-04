"""GET /api/reports, GET /api/reports/{name}, POST /api/write-report.

Report listing and generation. Write-report dispatches to the job store
(202 + job_id); read endpoints return synchronously.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agent_hum_crawler.api.job_store import JOB_STORE

router = APIRouter()

_ROOT = Path(__file__).resolve().parents[5]
_REPORTS_DIR = _ROOT / "reports"


# ── helpers ───────────────────────────────────────────────────────────────


def _safe_report_path(name: str) -> Path | None:
    if not name or "/" in name or "\\" in name or not name.endswith(".md"):
        return None
    p = (_REPORTS_DIR / name).resolve()
    if p.parent != _REPORTS_DIR.resolve() or not p.exists():
        return None
    return p


def _list_reports() -> list[dict]:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for path in _REPORTS_DIR.glob("*.md"):
        stat = path.stat()
        out.append({"name": path.name, "size": stat.st_size, "modified": stat.st_mtime})
    out.sort(key=lambda x: x["modified"], reverse=True)
    return out


# ── Request model ─────────────────────────────────────────────────────────


class WriteReportRequest(BaseModel):
    countries: str = "Madagascar,Mozambique"
    disaster_types: str = "cyclone/storm,flood"
    limit_cycles: int = Field(20, ge=1, le=200)
    limit_events: int = Field(30, ge=1, le=1000)
    max_age_days: int = Field(30, ge=1, le=3650)
    country_min_events: int = Field(1, ge=0)
    max_per_connector: int = Field(8, ge=0)
    max_per_source: int = Field(4, ge=0)
    report_template: str = "config/report_template.brief.json"
    use_llm: bool = False


# ── Worker ────────────────────────────────────────────────────────────────


def _do_write_report(req: WriteReportRequest) -> dict:
    from pathlib import Path as _Path
    from agent_hum_crawler.feature_flags import get_feature_flag
    from agent_hum_crawler.reporting import (
        build_graph_context,
        evaluate_report_quality,
        load_report_template,
        render_long_form_report,
        write_report_file,
    )
    from agent_hum_crawler.settings import load_environment

    load_environment()

    template_path = _Path(req.report_template) if req.report_template else None
    template = load_report_template(template_path)
    sections = template.get("sections", {})
    required_sections = [
        str(sections.get("executive_summary", "Executive Summary")),
        str(sections.get("incident_highlights", "Incident Highlights")),
        str(sections.get("source_reliability", "Source and Connector Reliability Snapshot")),
        str(sections.get("risk_outlook", "Risk Outlook")),
        str(sections.get("method", "Method")),
    ]
    countries = [c.strip() for c in req.countries.split(",") if c.strip()]
    disaster_types = [d.strip() for d in req.disaster_types.split(",") if d.strip()]
    strict_filters = bool(get_feature_flag("report_strict_filters_default", True))

    graph_context = build_graph_context(
        countries=countries,
        disaster_types=disaster_types,
        limit_cycles=req.limit_cycles,
        limit_events=req.limit_events,
        strict_filters=strict_filters,
        max_age_days=req.max_age_days,
        country_min_events=req.country_min_events,
        max_per_connector=req.max_per_connector,
        max_per_source=req.max_per_source,
    )
    report = render_long_form_report(
        graph_context=graph_context,
        title="Disaster Intelligence Report",
        use_llm=req.use_llm,
        template_path=template_path,
    )
    quality = evaluate_report_quality(report_markdown=report, required_sections=required_sections)
    out = write_report_file(report_markdown=report)

    return {
        "status": "ok" if quality.get("status") == "pass" else "quality_warning",
        "report_path": str(out),
        "meta": graph_context.get("meta", {}),
        "llm_used": "AI Assisted: Yes" in report,
        "report_quality": quality,
    }


# ── Routes ────────────────────────────────────────────────────────────────


@router.get("/reports")
def list_reports() -> dict:
    return {"reports": _list_reports()}


@router.get("/reports/{name}")
def get_report(name: str) -> dict:
    path = _safe_report_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"name": path.name, "markdown": path.read_text(encoding="utf-8")}


@router.post("/write-report", status_code=202)
def write_report(body: WriteReportRequest) -> dict:
    """Generate a report in the background. Poll GET /api/jobs/{job_id}."""
    job_id = JOB_STORE.submit(lambda _b=body: _do_write_report(_b))
    return {"job_id": job_id, "status": "queued"}

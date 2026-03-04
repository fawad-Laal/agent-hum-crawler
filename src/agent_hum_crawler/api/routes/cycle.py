"""POST /api/run-cycle, POST /api/source-check, POST /api/run-pipeline.

All three are long-running → dispatched to the shared :data:`JOB_STORE`
and return 202 immediately with a ``job_id``.  The frontend polls
``GET /api/jobs/{job_id}`` until ``status == "done"``.

Direct function calls (no subprocess) keep the process alive and share
the already-initialised DB connection pool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agent_hum_crawler.api.job_store import JOB_STORE

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────


class RunCycleRequest(BaseModel):
    countries: str = "Madagascar,Mozambique"
    disaster_types: str = "cyclone/storm,flood"
    limit: int = Field(10, ge=1, le=500)
    max_age_days: int = Field(30, ge=1, le=3650)


class SourceCheckRequest(BaseModel):
    countries: str = "Madagascar,Mozambique"
    disaster_types: str = "cyclone/storm,flood"
    limit: int = Field(20, ge=1, le=200)
    max_age_days: int = Field(30, ge=1, le=3650)


class RunPipelineRequest(BaseModel):
    countries: str = "Madagascar,Mozambique"
    disaster_types: str = "cyclone/storm,flood"
    report_title: str = "Disaster Intelligence Report"
    sa_title: str = "Situation Analysis"
    event_name: str = ""
    event_type: str = ""
    period: str = ""
    limit_cycles: int = Field(20, ge=1, le=200)
    limit_events: int = Field(80, ge=1, le=1000)
    max_age_days: int = Field(30, ge=1, le=3650)
    use_llm: bool = False


# ── Worker functions (run in background thread) ───────────────────────────


def _do_run_cycle(req: RunCycleRequest) -> dict:
    from agent_hum_crawler.alerts import build_alert_contract
    from agent_hum_crawler.config import RuntimeConfig
    from agent_hum_crawler.cycle import run_cycle_once
    from agent_hum_crawler.database import init_db
    from agent_hum_crawler.settings import load_environment

    load_environment()
    init_db()

    countries = [c.strip() for c in req.countries.split(",") if c.strip()]
    disaster_types = [d.strip() for d in req.disaster_types.split(",") if d.strip()]
    config = RuntimeConfig(countries=countries, disaster_types=disaster_types, max_item_age_days=req.max_age_days)

    result = run_cycle_once(config=config, limit=req.limit, include_content=True)
    alert_contract = build_alert_contract(result.events, interval_minutes=30)
    warnings: list[str] = [
        w.strip()
        for m in result.connector_metrics
        for w in (m.get("warnings") or [])
        if isinstance(w, str) and w.strip()
    ]
    return {
        "status": "ok",
        "cycle_id": result.cycle_id,
        "summary": result.summary,
        "connector_count": result.connector_count,
        "raw_item_count": result.raw_item_count,
        "event_count": result.event_count,
        "llm_enrichment": result.llm_enrichment,
        "alerts_contract": alert_contract,
        "connector_metrics": result.connector_metrics,
        "warnings": warnings,
    }


def _do_source_check(req: SourceCheckRequest) -> dict:
    from agent_hum_crawler.config import RuntimeConfig
    from agent_hum_crawler.cycle import run_source_check
    from agent_hum_crawler.settings import load_environment

    load_environment()

    countries = [c.strip() for c in req.countries.split(",") if c.strip()]
    disaster_types = [d.strip() for d in req.disaster_types.split(",") if d.strip()]
    config = RuntimeConfig(countries=countries, disaster_types=disaster_types, max_item_age_days=req.max_age_days)

    report = run_source_check(config=config, limit=req.limit, include_content=False)
    warnings: list[str] = [
        w.strip()
        for m in report.connector_metrics
        for w in (m.get("warnings") or [])
        if isinstance(w, str) and w.strip()
    ]
    return {
        "status": "ok",
        "connector_count": report.connector_count,
        "raw_item_count": report.raw_item_count,
        "working_sources": sum(1 for s in report.source_checks if s.get("working")),
        "total_sources": len(report.source_checks),
        "stale_sources": sum(1 for s in report.source_checks if s.get("freshness_status") == "stale"),
        "demoted_sources": sum(1 for s in report.source_checks if s.get("status") == "demoted_stale"),
        "warnings": warnings,
        "source_checks": report.source_checks,
        "connector_metrics": report.connector_metrics,
    }


def _do_run_pipeline(req: RunPipelineRequest) -> dict:
    from agent_hum_crawler.coordinator import PipelineCoordinator
    from agent_hum_crawler.database import init_db
    from agent_hum_crawler.settings import load_environment

    load_environment()
    init_db()

    countries = [c.strip() for c in req.countries.split(",") if c.strip()]
    disaster_types = [d.strip() for d in req.disaster_types.split(",") if d.strip()]

    coord = PipelineCoordinator(
        countries=countries,
        disaster_types=disaster_types,
        limit_cycles=req.limit_cycles,
        limit_events=req.limit_events,
        max_age_days=req.max_age_days,
    )
    coord.run_pipeline(
        report_title=req.report_title,
        sa_title=req.sa_title,
        event_name=req.event_name,
        event_type=req.event_type,
        period=req.period,
        use_llm=req.use_llm,
        write_files=True,
    )
    return coord.summary_dict()


# ── Route handlers ────────────────────────────────────────────────────────


@router.post("/run-cycle", status_code=202)
def run_cycle(body: RunCycleRequest) -> dict:
    """Start a collection cycle. Returns job token; poll GET /api/jobs/{job_id}."""
    job_id = JOB_STORE.submit(lambda _b=body: _do_run_cycle(_b), exclusive=True)
    return {"job_id": job_id, "status": "queued"}


@router.post("/source-check", status_code=202)
def source_check(body: SourceCheckRequest) -> dict:
    """Run a source freshness + connectivity check."""
    job_id = JOB_STORE.submit(lambda _b=body: _do_source_check(_b))
    return {"job_id": job_id, "status": "queued"}


@router.post("/run-pipeline", status_code=202)
def run_pipeline(body: RunPipelineRequest) -> dict:
    """Run the full evidence → report → SA pipeline."""
    job_id = JOB_STORE.submit(lambda _b=body: _do_run_pipeline(_b), exclusive=True)
    return {"job_id": job_id, "status": "queued"}

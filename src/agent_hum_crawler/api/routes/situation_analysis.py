"""POST /api/write-situation-analysis — generate OCHA-style Situation Analysis.

Worker runs directly via :func:`write_situation_analysis` (no subprocess).
Returns 202 + job token; poll ``GET /api/jobs/{job_id}`` for the result.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agent_hum_crawler.api.job_store import JOB_STORE

router = APIRouter()

_ROOT = Path(__file__).resolve().parents[5]
_REPORTS_DIR = _ROOT / "reports"


class WriteSARequest(BaseModel):
    countries: str = "Madagascar,Mozambique"
    disaster_types: str = "cyclone/storm,flood"
    title: str = "Situation Analysis"
    event_name: str = ""
    event_type: str = ""
    period: str = ""
    sa_template: str = "config/report_template.situation_analysis.json"
    limit_cycles: int = Field(20, ge=1, le=200)
    limit_events: int = Field(80, ge=1, le=1000)
    max_age_days: int | None = None
    use_llm: bool = False
    quality_gate: bool = False


def _do_write_sa(req: WriteSARequest) -> dict:
    from agent_hum_crawler.database import init_db
    from agent_hum_crawler.settings import load_environment
    from agent_hum_crawler.situation_analysis import write_situation_analysis

    load_environment()
    init_db()

    import subprocess, sys
    from datetime import datetime, UTC
    ts = subprocess.run(
        [sys.executable, "-c",
         "from datetime import datetime, UTC; print(datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ'))"],
        text=True, capture_output=True, check=False, cwd=_ROOT,
    ).stdout.strip() or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    out_path = _REPORTS_DIR / f"situation-analysis-{ts}.md"
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    countries = [c.strip() for c in req.countries.split(",") if c.strip()]
    disaster_types = [d.strip() for d in req.disaster_types.split(",") if d.strip()]
    template_path = Path(req.sa_template) if req.sa_template else None

    result = write_situation_analysis(
        countries=countries,
        disaster_types=disaster_types,
        title=req.title,
        event_name=req.event_name,
        event_type=req.event_type,
        period=req.period,
        template_path=template_path,
        use_llm=req.use_llm,
        limit_cycles=req.limit_cycles,
        limit_events=req.limit_events,
        max_age_days=req.max_age_days,
        output_path=out_path,
        quality_gate=req.quality_gate,
    )

    markdown = ""
    if out_path.exists():
        markdown = out_path.read_text(encoding="utf-8")
    elif result.get("report_path"):
        p = Path(result["report_path"])
        if p.exists():
            markdown = p.read_text(encoding="utf-8")

    result["markdown"] = markdown
    result["output_file"] = out_path.name
    return result


@router.post("/write-situation-analysis", status_code=202)
def write_situation_analysis_endpoint(body: WriteSARequest) -> dict:
    """Generate a Situation Analysis. Returns job token; poll for result."""
    job_id = JOB_STORE.submit(lambda _b=body: _do_write_sa(_b))
    return {"job_id": job_id, "status": "queued"}

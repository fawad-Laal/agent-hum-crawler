"""GET /api/jobs/{job_id} — poll job status / retrieve result."""

from fastapi import APIRouter, HTTPException

from agent_hum_crawler.api.job_store import JOB_STORE

router = APIRouter()


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    """Return the current status (and result when done) for a background job."""
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return JOB_STORE.response(job)

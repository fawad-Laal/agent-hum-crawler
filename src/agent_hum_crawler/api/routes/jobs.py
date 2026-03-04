"""GET /api/jobs/{job_id}        — poll job status / retrieve result.
GET /api/jobs/{job_id}/stream  — SSE stream of job progress events.
"""

import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent_hum_crawler.api.job_store import JOB_STORE

router = APIRouter()

_STREAM_INTERVAL = 0.75   # seconds between status pushes
_STREAM_TIMEOUT = 20 * 60  # hard cap: 20 minutes
_HEARTBEAT_EVERY = 15     # seconds between keep-alive comments


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    """Return the current status (and result when done) for a background job."""
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return JOB_STORE.response(job)


@router.get("/jobs/{job_id}/stream")
def stream_job(job_id: str) -> StreamingResponse:
    """Server-Sent Events stream of job status updates.

    Pushes a JSON event once per ~0.75 s until the job reaches *done* or
    *error* state, then closes the stream.  A heartbeat comment
    (``": ping"``) is sent every 15 s to keep connections alive through
    proxies and nginx. The stream closes automatically after 20 minutes.

    Client example::

        const es = new EventSource(`/api/jobs/${jobId}/stream`);
        es.onmessage = (e) => {
            const data = JSON.parse(e.data);
            // { job_id, status, result?, error? }
        };
    """
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    def _generate():
        deadline = time.monotonic() + _STREAM_TIMEOUT
        last_heartbeat = time.monotonic()

        while time.monotonic() < deadline:
            current = JOB_STORE.get(job_id)
            if current is None:
                yield (
                    f"data: {json.dumps({'job_id': job_id, 'status': 'error', "
                    f"'error': 'Job record lost'})}\n\n"
                )
                return

            yield f"data: {json.dumps(JOB_STORE.response(current))}\n\n"

            if current.status in ("done", "error"):
                return

            now = time.monotonic()
            if now - last_heartbeat >= _HEARTBEAT_EVERY:
                yield ": ping\n\n"
                last_heartbeat = now

            time.sleep(_STREAM_INTERVAL)

        # Timeout — inform the client
        yield (
            f"data: {json.dumps({'job_id': job_id, 'status': 'error', "
            f"'error': 'Stream timed out after 20 minutes'})}\n\n"
        )

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx output buffering
            "Connection": "keep-alive",
        },
    )

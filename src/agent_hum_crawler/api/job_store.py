"""Shared in-process job store for async long-running tasks.

All routes that spawn background work use :data:`JOB_STORE` singleton.
The exclusive semaphore ensures at most one *cycle* or *pipeline* runs at a time,
which prevents duplicate crawls from concurrent UI requests.

Usage::

    from agent_hum_crawler.api.job_store import JOB_STORE

    @router.post("/run-cycle", status_code=202)
    def run_cycle(body: RunCycleRequest) -> dict:
        job_id = JOB_STORE.submit(lambda: _do_run_cycle(body), exclusive=True)
        return {"job_id": job_id, "status": "queued"}
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Job:
    """A single tracked background task."""

    job_id: str
    status: str = "queued"          # queued | running | done | error
    result: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    """Thread-safe in-process job registry with optional exclusive-access semaphore.

    Parameters
    ----------
    max_exclusive:
        Maximum number of *exclusive* (cycle/pipeline) jobs that may run
        concurrently. Defaults to 1 so the crawler never double-runs.
    """

    def __init__(self, *, max_exclusive: int = 1) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._sem = threading.Semaphore(max_exclusive)

    # ── public API ────────────────────────────────────────────────────────

    def submit(
        self,
        fn: Callable[[], dict[str, Any]],
        *,
        exclusive: bool = False,
    ) -> str:
        """Start *fn* in a daemon thread. Returns job_id immediately.

        If *exclusive=True* and the semaphore is exhausted the job is
        immediately put into *error* state (non-blocking rejection).
        """
        job_id = uuid.uuid4().hex[:8]
        job = Job(job_id=job_id, status="queued")
        with self._lock:
            self._jobs[job_id] = job

        # Capture fn via default arg to avoid late-binding closure bugs
        def _run(_fn: Callable[[], dict[str, Any]] = fn) -> None:
            sem = self._sem if exclusive else None
            if sem is not None and not sem.acquire(blocking=False):
                with self._lock:
                    job.status = "error"
                    job.error = (
                        "Another cycle or pipeline is already running — "
                        "try again shortly."
                    )
                return
            try:
                with self._lock:
                    job.status = "running"
                result = _fn()
                with self._lock:
                    job.status = "done"
                    job.result = result
            except Exception as exc:  # noqa: BLE001
                import traceback
                with self._lock:
                    job.status = "error"
                    job.error = f"{type(exc).__name__}: {exc}"
                traceback.print_exc()
            finally:
                if sem is not None:
                    try:
                        sem.release()
                    except ValueError:
                        pass

        threading.Thread(target=_run, daemon=True, name=f"job-{job_id}").start()
        return job_id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def response(self, job: Job) -> dict[str, Any]:
        """Serialise a job to a JSON-safe dict for the API response."""
        base: dict[str, Any] = {"job_id": job.job_id, "status": job.status}
        if job.status == "done" and job.result is not None:
            base["result"] = job.result
        if job.status == "error" and job.error is not None:
            base["error"] = job.error
        return base


# ── Singleton used by all route modules ───────────────────────────────────

JOB_STORE = JobStore()

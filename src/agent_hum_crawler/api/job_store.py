"""Shared in-process (and optionally Redis-backed) job store.

All routes that spawn background work use the :data:`JOB_STORE` singleton.
The exclusive semaphore ensures at most one *cycle* or *pipeline* runs at a
time, preventing duplicate crawls from concurrent UI requests.

**Redis caching (optional)**

Set ``REDIS_URL`` in the environment (e.g. ``redis://localhost:6379/0``) to
enable Redis-backed job storage.  Completed jobs are kept for
:data:`REDIS_JOB_TTL` seconds (default 24 h) so the result survives a server
restart.  If the Redis connection fails at startup the store transparently
falls back to the in-process implementation â€” no configuration change needed.

Usage::

    from agent_hum_crawler.api.job_store import JOB_STORE

    @router.post("/run-cycle", status_code=202)
    def run_cycle(body: RunCycleRequest) -> dict:
        job_id = JOB_STORE.submit(lambda: _do_run_cycle(body), exclusive=True)
        return {"job_id": job_id, "status": "queued"}
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


# â”€â”€ Job data model â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class Job:
    """A single tracked background task."""

    job_id: str
    status: str = "queued"          # queued | running | done | error
    result: dict[str, Any] | None = None
    error: str | None = None


# â”€â”€ Shared TTL constant for Redis-cached jobs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

REDIS_JOB_TTL = int(os.environ.get("REDIS_JOB_TTL", 86_400))  # 24 h default


# â”€â”€ Protocol: both backends implement the same public surface â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class _JobBackend(Protocol):
    def submit(
        self,
        fn: Callable[[], dict[str, Any]],
        *,
        exclusive: bool = False,
    ) -> str: ...

    def get(self, job_id: str) -> Job | None: ...

    def response(self, job: Job) -> dict[str, Any]: ...


# â”€â”€ In-process implementation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class JobStore:
    """Thread-safe in-process job registry with optional exclusive-access semaphore.

    Parameters
    ----------
    max_exclusive:
        Maximum number of *exclusive* (cycle/pipeline) jobs that may run
        concurrently.  Defaults to 1 so the crawler never double-runs.
    """

    def __init__(self, *, max_exclusive: int = 1) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._sem = threading.Semaphore(max_exclusive)

    # â”€â”€ public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

        def _run(_fn: Callable[[], dict[str, Any]] = fn) -> None:
            sem = self._sem if exclusive else None
            if sem is not None and not sem.acquire(blocking=False):
                with self._lock:
                    job.status = "error"
                    job.error = (
                        "Another cycle or pipeline is already running â€” "
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


# â”€â”€ Redis-backed implementation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class RedisJobStore:
    """Redis-backed job store.  Jobs survive server restarts and are
    visible across multiple worker processes.

    Each job is stored as a Redis hash at key ``moltis:job:<job_id>``
    with a TTL of :data:`REDIS_JOB_TTL` seconds.

    Parameters
    ----------
    redis_url:
        Redis connection URL (e.g. ``redis://localhost:6379/0``).
    max_exclusive:
        Maximum concurrent exclusive (cycle/pipeline) jobs.  Enforced by a
        :class:`threading.Semaphore` â€” process-local only.  For multi-process
        deployments use a Redis-based distributed lock instead.
    ttl:
        Seconds to keep completed/failed job records in Redis.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        max_exclusive: int = 1,
        ttl: int = REDIS_JOB_TTL,
    ) -> None:
        import redis as _redis  # type: ignore[import-untyped]

        self._redis: Any = _redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl
        self._sem = threading.Semaphore(max_exclusive)
        # Verify connection immediately so the factory can catch errors
        self._redis.ping()

    # â”€â”€ private helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _key(self, job_id: str) -> str:
        return f"moltis:job:{job_id}"

    def _write(self, job: Job) -> None:
        key = self._key(job.job_id)
        mapping: dict[str, str] = {
            "job_id": job.job_id,
            "status": job.status,
        }
        if job.result is not None:
            mapping["result"] = json.dumps(job.result)
        if job.error is not None:
            mapping["error"] = job.error
        self._redis.hset(key, mapping=mapping)
        self._redis.expire(key, self._ttl)

    def _read(self, job_id: str) -> Job | None:
        raw: dict[str, str] = self._redis.hgetall(self._key(job_id))
        if not raw:
            return None
        result = None
        if "result" in raw:
            try:
                result = json.loads(raw["result"])
            except json.JSONDecodeError:
                result = None
        return Job(
            job_id=raw.get("job_id", job_id),
            status=raw.get("status", "unknown"),
            result=result,
            error=raw.get("error"),
        )

    # â”€â”€ public API (same surface as JobStore) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def submit(
        self,
        fn: Callable[[], dict[str, Any]],
        *,
        exclusive: bool = False,
    ) -> str:
        """Dispatch *fn* to a daemon thread. Job state written to Redis."""
        job_id = uuid.uuid4().hex[:8]
        job = Job(job_id=job_id, status="queued")
        self._write(job)

        def _run(_fn: Callable[[], dict[str, Any]] = fn) -> None:
            sem = self._sem if exclusive else None
            if sem is not None and not sem.acquire(blocking=False):
                job.status = "error"
                job.error = (
                    "Another cycle or pipeline is already running â€” "
                    "try again shortly."
                )
                self._write(job)
                return
            try:
                job.status = "running"
                self._write(job)
                result = _fn()
                job.status = "done"
                job.result = result
                self._write(job)
            except Exception as exc:  # noqa: BLE001
                import traceback
                job.status = "error"
                job.error = f"{type(exc).__name__}: {exc}"
                self._write(job)
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
        return self._read(job_id)

    def response(self, job: Job) -> dict[str, Any]:
        base: dict[str, Any] = {"job_id": job.job_id, "status": job.status}
        if job.status == "done" and job.result is not None:
            base["result"] = job.result
        if job.status == "error" and job.error is not None:
            base["error"] = job.error
        return base


# â”€â”€ Factory: pick Redis if REDIS_URL is set, else in-process â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _make_job_store() -> JobStore | RedisJobStore:
    """Return a :class:`RedisJobStore` if ``REDIS_URL`` is configured and the
    ``redis`` package is importable, otherwise return an in-process
    :class:`JobStore`.
    """
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url:
        try:
            store = RedisJobStore(redis_url)
            print(f"[job_store] Using Redis job store: {redis_url}", flush=True)
            return store
        except Exception as exc:
            print(
                f"[job_store] Redis unavailable ({exc}); "
                "falling back to in-process store.",
                flush=True,
            )
    return JobStore()


# â”€â”€ Singleton used by all route modules â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

JOB_STORE: JobStore | RedisJobStore = _make_job_store()


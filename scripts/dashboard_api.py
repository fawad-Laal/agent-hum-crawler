"""Minimal local API for the crawler dashboard.

Exposes existing CLI functionality for a lightweight React frontend.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from agent_hum_crawler.feature_flags import load_feature_flags
from agent_hum_crawler.config import ALLOWED_DISASTER_TYPES
from agent_hum_crawler.source_credibility import tier_label
from agent_hum_crawler.database import build_extraction_diagnostics_report


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"


def _monitoring_db_path() -> Path:
    """Return the path to the monitoring database (same as database.default_db_path)."""
    return Path.home() / ".moltis" / "agent-hum-crawler" / "monitoring.db"


def _db_query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT against the monitoring DB and return rows as dicts."""
    db_path = _monitoring_db_path()
    if not db_path.exists():
        return []
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


E2E_DIR = ROOT / "artifacts" / "e2e"
PROFILE_FILE = ROOT / "config" / "dashboard_workbench_profiles.json"
COUNTRY_SOURCES_FILE = ROOT / "config" / "country_sources.json"


def _latest_credibility_distribution() -> dict:
    """Parse the most recent report for by_credibility_tier data."""
    candidates = sorted(REPORTS_DIR.glob("report-*.md"), reverse=True)
    for f in candidates[:5]:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        dist: dict[str, int] = {}
        for tier_num in range(1, 5):
            label = tier_label(tier_num)
            pattern = rf"\b{re.escape(label)}\b.*?(\d+)"
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                dist[f"tier_{tier_num}"] = int(m.group(1))
        if dist:
            return {"source": f.name, **dist}
    return {}


def _json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


def _parse_json_payload(text: str) -> tuple[dict | list | None, str]:
    """Parse JSON even when CLI prepends warning lines before payload."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch not in "{[":
            continue
        try:
            payload, end = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        trailing = text[i + end :].strip()
        if trailing:
            continue
        leading = text[:i].strip()
        return payload, leading
    return None, text.strip()


def _run_cli(args: list[str], timeout: int = 30) -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "agent_hum_crawler.main", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "command": args, "error": f"CLI timed out after {timeout}s"}
    if proc.returncode != 0:
        return {
            "status": "error",
            "command": args,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    payload, leading = _parse_json_payload(proc.stdout)
    if payload is None:
        return {"status": "error", "command": args, "stdout": proc.stdout, "stderr": proc.stderr}
    if isinstance(payload, dict) and leading:
        warnings = [line.strip() for line in leading.splitlines() if line.strip()]
        if warnings:
            payload["warnings"] = warnings
    return payload


# ── In-process job store with concurrency guard ─────────────────────────────

# Completed/error jobs older than this are purged on the next submit()
_JOB_TTL_SECONDS = 300  # 5 minutes  (R15)


@dataclass
class _Job:
    job_id: str
    job_type: str = "generic"  # cycle | write-report | source-check | sa | workbench | pipeline
    status: str = "queued"    # queued | running | done | error
    result: dict[str, Any] | None = None
    error: str | None = None
    queued_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    completed_at: float | None = None


class _JobStore:
    """Thread-safe job registry with exclusive + per-type semaphores.  (R13-R15)

    - *exclusive* jobs (cycle, pipeline) share one semaphore — only one runs
      at a time, returning an actionable 409 error when full.
    - LLM-backed jobs (sa, write-report with LLM, pipeline with LLM) share
      a separate semaphore — returns actionable 429 when full.  (R14)
    - Completed/error jobs older than _JOB_TTL_SECONDS are purged on each
      submit() call to bound memory usage.  (R15)
    - Timing fields (queued_at, started_at, completed_at) are tracked so the
      API can surface elapsed_ms and wait_ms to operators.  (R18)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}
        # At most one heavy exclusive job (cycle / pipeline) at a time
        self._cycle_sem = threading.Semaphore(1)
        # At most one LLM-backed job at a time (SA, write-report+LLM, pipeline+LLM)
        self._llm_sem = threading.Semaphore(1)

    def _purge(self) -> None:
        """Remove stale completed/error jobs (called under self._lock)."""
        threshold = time.monotonic() - _JOB_TTL_SECONDS
        stale = [
            jid
            for jid, j in self._jobs.items()
            if j.status in ("done", "error")
            and j.completed_at is not None
            and j.completed_at < threshold
        ]
        for jid in stale:
            del self._jobs[jid]

    def submit(
        self,
        fn: Callable[[], dict[str, Any]],
        *,
        exclusive: bool = False,
        job_type: str = "generic",
        llm: bool = False,
    ) -> str:
        """Dispatch *fn* to a daemon thread. Returns job_id immediately."""
        job_id = uuid.uuid4().hex[:8]
        job = _Job(job_id=job_id, job_type=job_type)
        with self._lock:
            self._purge()
            self._jobs[job_id] = job

        # Capture fn in default arg to avoid late-binding closure issues
        def _run(_fn: Callable[[], dict[str, Any]] = fn) -> None:
            cycle_sem = self._cycle_sem if exclusive else None
            llm_sem = self._llm_sem if llm else None

            if cycle_sem is not None and not cycle_sem.acquire(blocking=False):
                with self._lock:
                    job.status = "error"
                    job.completed_at = time.monotonic()
                    job.error = (
                        "409: Another cycle or pipeline is already running "
                        "\u2014 try again shortly."
                    )
                return

            if llm_sem is not None and not llm_sem.acquire(blocking=False):
                if cycle_sem is not None:
                    try:
                        cycle_sem.release()
                    except ValueError:
                        pass
                with self._lock:
                    job.status = "error"
                    job.completed_at = time.monotonic()
                    job.error = (
                        "429: An LLM job is already in progress "
                        "\u2014 try again once it completes."
                    )
                return

            try:
                with self._lock:
                    job.status = "running"
                    job.started_at = time.monotonic()
                result = _fn()
                with self._lock:
                    job.status = "done"
                    job.completed_at = time.monotonic()
                    job.result = result
            except Exception as exc:  # noqa: BLE001
                import traceback
                with self._lock:
                    job.status = "error"
                    job.completed_at = time.monotonic()
                    job.error = f"{type(exc).__name__}: {exc}"
                traceback.print_exc()
            finally:
                if cycle_sem is not None:
                    try:
                        cycle_sem.release()
                    except ValueError:
                        pass
                if llm_sem is not None:
                    try:
                        llm_sem.release()
                    except ValueError:
                        pass

        threading.Thread(target=_run, daemon=True, name=f"job-{job_id}").start()
        return job_id

    def get(self, job_id: str) -> _Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def to_response(self, job: _Job) -> dict[str, Any]:
        now = time.monotonic()
        base: dict[str, Any] = {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status,
        }
        # Operator-facing timing (R18)
        if job.started_at is not None:
            ref = job.completed_at if job.completed_at is not None else now
            base["elapsed_ms"] = round((ref - job.started_at) * 1000)
        if job.started_at is not None:
            base["wait_ms"] = round(
                (job.started_at - job.queued_at) * 1000
            )
        if job.status == "done" and job.result is not None:
            base["result"] = job.result
        if job.status == "error" and job.error is not None:
            base["error"] = job.error
        return base


_JOB_STORE = _JobStore()


def _list_reports() -> list[dict]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for path in REPORTS_DIR.glob("*.md"):
        stat = path.stat()
        out.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    out.sort(key=lambda x: x["modified"], reverse=True)
    return out


def _latest_e2e_summary() -> dict:
    if not E2E_DIR.exists():
        return {}
    candidates = sorted([p for p in E2E_DIR.iterdir() if p.is_dir()], reverse=True)
    for d in candidates:
        summary = d / "summary.json"
        if summary.exists():
            try:
                payload = json.loads(summary.read_text(encoding="utf-8"))
                payload["artifact_dir"] = str(d)
                return payload
            except json.JSONDecodeError:
                continue
    return {}


def _quality_trend(window: int = 10) -> list[dict]:
    out: list[dict] = []
    for i in range(1, max(window, 1) + 1):
        q = _run_cli(["quality-report", "--limit", str(i)])
        if not isinstance(q, dict) or "duplicate_rate_estimate" not in q:
            continue
        out.append(
            {
                "limit": i,
                "duplicate_rate_estimate": q.get("duplicate_rate_estimate", 0.0),
                "traceable_rate": q.get("traceable_rate", 0.0),
                "llm_enrichment_rate": q.get("llm_enrichment_rate", 0.0),
                "citation_coverage_rate": q.get("citation_coverage_rate", 0.0),
                "events_analyzed": q.get("events_analyzed", 0),
            }
        )
    return out


def _safe_report_path(name: str) -> Path | None:
    if not name or "/" in name or "\\" in name:
        return None
    if not name.endswith(".md"):
        return None
    p = (REPORTS_DIR / name).resolve()
    if p.parent != REPORTS_DIR.resolve():
        return None
    if not p.exists():
        return None
    return p


def _default_workbench_profile() -> dict:
    flags = load_feature_flags()
    return {
        "countries": "Madagascar,Mozambique",
        "disaster_types": "cyclone/storm,flood",
        "max_age_days": int(flags.get("max_item_age_days_default", 30) or 30),
        "limit_cycles": 20,
        "limit_events": 30,
        "report_template": "config/report_template.brief.json",
        "country_min_events": 1,
        "max_per_connector": 8,
        "max_per_source": 4,
    }


def _normalize_profile(payload: dict | None) -> dict:
    src = payload or {}
    base = _default_workbench_profile()
    base["countries"] = str(src.get("countries", base["countries"]))
    base["disaster_types"] = str(src.get("disaster_types", base["disaster_types"]))
    try:
        base["limit_cycles"] = int(src.get("limit_cycles", base["limit_cycles"]))
    except Exception:
        pass
    try:
        base["limit_events"] = int(src.get("limit_events", base["limit_events"]))
    except Exception:
        pass
    try:
        base["max_age_days"] = int(src.get("max_age_days", base["max_age_days"]))
    except Exception:
        pass
    base["limit_cycles"] = max(1, min(base["limit_cycles"], 200))
    base["limit_events"] = max(1, min(base["limit_events"], 500))
    base["max_age_days"] = max(1, min(int(base["max_age_days"]), 3650))
    try:
        base["country_min_events"] = max(0, int(src.get("country_min_events", base.get("country_min_events", 1))))
    except Exception:
        base["country_min_events"] = 1
    try:
        base["max_per_connector"] = max(0, int(src.get("max_per_connector", base.get("max_per_connector", 8))))
    except Exception:
        base["max_per_connector"] = 8
    try:
        base["max_per_source"] = max(0, int(src.get("max_per_source", base.get("max_per_source", 4))))
    except Exception:
        base["max_per_source"] = 4
    template = str(src.get("report_template", base["report_template"]))
    if template.startswith("config/") and template.endswith(".json"):
        base["report_template"] = template
    return base


def _load_profile_store() -> dict:
    if not PROFILE_FILE.exists():
        return {"presets": {}, "last_profile": _default_workbench_profile()}
    try:
        payload = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"presets": {}, "last_profile": _default_workbench_profile()}
    presets = payload.get("presets", {})
    if not isinstance(presets, dict):
        presets = {}
    clean_presets: dict[str, dict] = {}
    for k, v in presets.items():
        name = str(k).strip()
        if not name:
            continue
        clean_presets[name] = _normalize_profile(v if isinstance(v, dict) else {})
    last_profile = payload.get("last_profile", {})
    if not isinstance(last_profile, dict):
        last_profile = {}
    return {"presets": clean_presets, "last_profile": _normalize_profile(last_profile)}


def _save_profile_store(store: dict) -> None:
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_FILE.write_text(json.dumps(store, indent=2), encoding="utf-8")


def _load_template(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _section_word_usage(markdown: str, section_titles: list[str]) -> dict[str, int]:
    lines = markdown.splitlines()
    sections: dict[str, list[str]] = {title: [] for title in section_titles}
    current: str | None = None
    title_set = {f"## {t}": t for t in section_titles}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current = title_set.get(stripped, None)
            continue
        if current:
            sections[current].append(line)
    usage: dict[str, int] = {}
    for title, content in sections.items():
        text = "\n".join(content)
        usage[title] = len(re.findall(r"\b[\w/-]+\b", text))
    return usage


def _build_workbench_report(
    *,
    countries: str,
    disaster_types: str,
    limit_cycles: int,
    limit_events: int,
    max_age_days: int,
    country_min_events: int,
    max_per_connector: int,
    max_per_source: int,
    template_path: str,
    use_llm: bool,
) -> dict:
    ts = subprocess.run(
        [sys.executable, "-c", "from datetime import datetime, UTC; print(datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ'))"],
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    ).stdout.strip()
    suffix = "ai" if use_llm else "det"
    out_path = REPORTS_DIR / f"workbench-{ts}-{suffix}.md"
    cmd = [
        "write-report",
        "--countries",
        countries,
        "--disaster-types",
        disaster_types,
        "--limit-cycles",
        str(limit_cycles),
        "--limit-events",
        str(limit_events),
        "--max-age-days",
        str(max_age_days),
        "--country-min-events",
        str(country_min_events),
        "--max-per-connector",
        str(max_per_connector),
        "--max-per-source",
        str(max_per_source),
        "--report-template",
        template_path,
        "--output",
        str(out_path),
    ]
    if use_llm:
        cmd.append("--use-llm")
    payload = _run_cli(cmd)
    markdown = ""
    if out_path.exists():
        markdown = out_path.read_text(encoding="utf-8")
    payload["markdown"] = markdown
    return payload


def _run_workbench(profile: dict) -> dict:
    profile = _normalize_profile(profile)
    countries = profile["countries"]
    disaster_types = profile["disaster_types"]
    limit_cycles = profile["limit_cycles"]
    limit_events = profile["limit_events"]
    max_age_days = profile["max_age_days"]
    country_min_events = profile["country_min_events"]
    max_per_connector = profile["max_per_connector"]
    max_per_source = profile["max_per_source"]
    template_path = profile["report_template"]

    tpl = _load_template(ROOT / template_path)
    section_map = tpl.get("sections", {}) if isinstance(tpl.get("sections"), dict) else {}
    limits = tpl.get("limits", {}) if isinstance(tpl.get("limits"), dict) else {}
    section_titles = [
        str(section_map.get("executive_summary", "Executive Summary")),
        str(section_map.get("incident_highlights", "Incident Highlights")),
        str(section_map.get("source_reliability", "Source and Connector Reliability Snapshot")),
        str(section_map.get("risk_outlook", "Risk Outlook")),
        str(section_map.get("method", "Method")),
    ]

    deterministic = _build_workbench_report(
        countries=countries,
        disaster_types=disaster_types,
        limit_cycles=limit_cycles,
        limit_events=limit_events,
        max_age_days=max_age_days,
        country_min_events=country_min_events,
        max_per_connector=max_per_connector,
        max_per_source=max_per_source,
        template_path=template_path,
        use_llm=False,
    )
    ai = _build_workbench_report(
        countries=countries,
        disaster_types=disaster_types,
        limit_cycles=limit_cycles,
        limit_events=limit_events,
        max_age_days=max_age_days,
        country_min_events=country_min_events,
        max_per_connector=max_per_connector,
        max_per_source=max_per_source,
        template_path=template_path,
        use_llm=True,
    )

    return {
        "profile": profile,
        "template": {
            "path": template_path,
            "sections": section_map,
            "limits": limits,
        },
        "deterministic": {
            **deterministic,
            "section_word_usage": _section_word_usage(
                str(deterministic.get("markdown", "")),
                section_titles,
            ),
        },
        "ai": {
            **ai,
            "section_word_usage": _section_word_usage(
                str(ai.get("markdown", "")),
                section_titles,
            ),
        },
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AHCDashboard/1.0"

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: N802
        # Redirect access logs to stdout to avoid PowerShell treating stderr as fatal errors
        print(f"[{self.address_string()}] {fmt % args}", flush=True)

    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._do_GET_inner()
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            try:
                self._send_json({"status": "error", "error": str(exc)}, status=500)
            except Exception:
                pass

    def _do_GET_inner(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return
        # ── Job status polling ──────────────────────────────────────────
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.removeprefix("/api/jobs/")
            job = _JOB_STORE.get(job_id)
            if not job:
                self._send_json({"error": "job not found"}, status=404)
                return
            self._send_json(_JOB_STORE.to_response(job))
            return
        if parsed.path == "/api/overview":
            from concurrent.futures import ThreadPoolExecutor, as_completed
            flags = load_feature_flags()
            # Run all expensive operations in parallel
            _cli_tasks = {
                "quality": ["quality-report", "--limit", "10"],
                "source_health": ["source-health", "--limit", "10"],
                "hardening": ["hardening-gate", "--limit", "10"],
                "cycles": ["show-cycles", "--limit", "20"],
            }
            _cli_results: dict = {}
            e2e_summary: dict = {}
            quality_trend: list = []
            credibility: dict = {}
            with ThreadPoolExecutor(max_workers=8) as pool:
                cli_futures = {pool.submit(_run_cli, cmd, 30): key for key, cmd in _cli_tasks.items()}
                fut_e2e = pool.submit(_latest_e2e_summary)
                fut_trend = pool.submit(_quality_trend, 10)
                fut_cred = pool.submit(_latest_credibility_distribution)
                for fut in as_completed(cli_futures):
                    key = cli_futures[fut]
                    try:
                        _cli_results[key] = fut.result()
                    except Exception as exc:
                        _cli_results[key] = {"status": "error", "error": str(exc)}
                try:
                    e2e_summary = fut_e2e.result()
                except Exception:
                    e2e_summary = {}
                try:
                    quality_trend = fut_trend.result()
                except Exception:
                    quality_trend = []
                try:
                    credibility = fut_cred.result()
                except Exception:
                    credibility = {}
            payload = {
                "quality": _cli_results.get("quality", {}),
                "source_health": _cli_results.get("source_health", {}),
                "hardening": _cli_results.get("hardening", {}),
                "cycles": _cli_results.get("cycles") if isinstance(_cli_results.get("cycles"), list) else [],
                "quality_trend": quality_trend,
                "latest_e2e_summary": e2e_summary,
                "feature_flags": flags,
                "credibility_distribution": credibility,
            }
            self._send_json(payload)
            return
        if parsed.path == "/api/reports":
            self._send_json({"reports": _list_reports()})
            return
        if parsed.path == "/api/workbench-profiles":
            self._send_json(_load_profile_store())
            return
        if parsed.path.startswith("/api/reports/"):
            name = parsed.path.split("/api/reports/", 1)[1]
            report_path = _safe_report_path(name)
            if not report_path:
                self._send_json({"error": "report not found"}, status=404)
                return
            self._send_json({"name": report_path.name, "markdown": report_path.read_text(encoding="utf-8")})
            return
        if parsed.path == "/api/system-info":
            rust_available = False
            try:
                from agent_hum_crawler.rust_accel import rust_available as _ra
                rust_available = _ra()
            except ImportError:
                pass
            self._send_json({
                "python_version": sys.version,
                "rust_available": rust_available,
                "allowed_disaster_types": sorted(ALLOWED_DISASTER_TYPES),
            })
            return
        # ── Database query endpoints ────────────────────────────────────────
        if parsed.path == "/api/db/cycles":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["50"])[0])
            limit = max(1, min(limit, 200))
            rows = _db_query(
                "SELECT * FROM cyclerun ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            db_path = _monitoring_db_path()
            self._send_json({"cycles": rows, "db_path": str(db_path), "count": len(rows)})
            return
        if parsed.path == "/api/db/events":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["100"])[0])
            limit = max(1, min(limit, 500))
            country = qs.get("country", [None])[0]
            disaster_type = qs.get("disaster_type", [None])[0]
            where_parts = []
            params: list = []
            if country:
                where_parts.append("country = ?")
                params.append(country)
            if disaster_type:
                where_parts.append("disaster_type LIKE ?")
                params.append(f"%{disaster_type}%")
            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            rows = _db_query(
                f"SELECT * FROM eventrecord {where_clause} ORDER BY id DESC LIMIT ?",
                tuple(params) + (limit,),
            )
            self._send_json({"events": rows, "count": len(rows)})
            return
        if parsed.path == "/api/db/raw-items":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["100"])[0])
            limit = max(1, min(limit, 500))
            rows = _db_query(
                "SELECT id, cycle_id, connector, source_type, title, url, published_at FROM rawitemrecord ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            self._send_json({"raw_items": rows, "count": len(rows)})
            return
        if parsed.path == "/api/db/feed-health":
            qs = parse_qs(parsed.query)
            limit = int(qs.get("limit", ["100"])[0])
            limit = max(1, min(limit, 500))
            rows = _db_query(
                "SELECT * FROM feedhealthrecord ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            self._send_json({"feed_health": rows, "count": len(rows)})
            return
        if parsed.path == "/api/db/extraction-diagnostics":
            qs = parse_qs(parsed.query)
            limit_cycles = int(qs.get("limit_cycles", ["20"])[0])
            limit_cycles = max(1, min(limit_cycles, 100))
            connector = qs.get("connector", [None])[0] or None
            try:
                report = build_extraction_diagnostics_report(
                    limit_cycles=limit_cycles,
                    connector=connector,
                )
                self._send_json(report)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=500)
            return
        if parsed.path == "/api/country-sources":
            data: dict = {}
            try:
                data = json.loads(COUNTRY_SOURCES_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
            countries_cfg = data.get("countries", {})
            global_cfg = data.get("global", {})
            country_list = sorted(countries_cfg.keys())
            # For each country, count feeds
            summary = []
            for c in country_list:
                entry = countries_cfg.get(c, {})
                feed_count = sum(
                    len(entry.get(cat, []))
                    for cat in ("government", "un", "ngo", "local_news")
                )
                summary.append({"country": c, "feed_count": feed_count, "sources": entry})
            global_feed_count = sum(
                len(global_cfg.get(cat, []))
                for cat in ("government", "un", "ngo", "local_news")
            )
            self._send_json({
                "countries": summary,
                "global_feed_count": global_feed_count,
                "global_sources": global_cfg,
            })
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._do_POST_inner()
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            try:
                self._send_json({"status": "error", "error": str(exc)}, status=500)
            except Exception:
                pass

    def _do_POST_inner(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/run-cycle":
            body = _json_body(self)
            cmd = [
                "run-cycle",
                "--countries",
                str(body.get("countries", "Madagascar,Mozambique")),
                "--disaster-types",
                str(body.get("disaster_types", "cyclone/storm,flood")),
                "--limit",
                str(int(body.get("limit", 10))),
                "--max-age-days",
                str(int(body.get("max_age_days", 30))),
                "--include-content",
            ]
            job_id = _JOB_STORE.submit(lambda _c=cmd: _run_cli(_c, timeout=300), exclusive=True, job_type="cycle")
            self._send_json({"job_id": job_id, "status": "queued"}, status=202)
            return
        if parsed.path == "/api/write-report":
            body = _json_body(self)
            cmd = [
                "write-report",
                "--countries",
                str(body.get("countries", "Madagascar,Mozambique")),
                "--disaster-types",
                str(body.get("disaster_types", "cyclone/storm,flood")),
                "--limit-cycles",
                str(int(body.get("limit_cycles", 20))),
                "--limit-events",
                str(int(body.get("limit_events", 30))),
                "--max-age-days",
                str(int(body.get("max_age_days", 30))),
                "--country-min-events",
                str(int(body.get("country_min_events", 1))),
                "--max-per-connector",
                str(int(body.get("max_per_connector", 8))),
                "--max-per-source",
                str(int(body.get("max_per_source", 4))),
                "--report-template",
                str(body.get("report_template", "config/report_template.brief.json")),
                "--enforce-report-quality",
            ]
            if bool(body.get("use_llm", False)):
                cmd.append("--use-llm")
            job_id = _JOB_STORE.submit(
                lambda _c=cmd: _run_cli(_c, timeout=300),
                job_type="write-report",
                llm=bool(body.get("use_llm", False)),
            )
            self._send_json({"job_id": job_id, "status": "queued"}, status=202)
            return
        if parsed.path == "/api/source-check":
            flags = load_feature_flags()
            if not bool(flags.get("source_check_endpoint_enabled", True)):
                self._send_json({"status": "error", "error": "source-check endpoint disabled by feature flag"}, status=403)
                return
            body = _json_body(self)
            cmd = [
                "source-check",
                "--countries",
                str(body.get("countries", "Madagascar,Mozambique")),
                "--disaster-types",
                str(body.get("disaster_types", "cyclone/storm,flood")),
                "--limit",
                str(int(body.get("limit", 20))),
                "--max-age-days",
                str(int(body.get("max_age_days", 30))),
            ]
            job_id = _JOB_STORE.submit(lambda _c=cmd: _run_cli(_c, timeout=120), job_type="source-check")
            self._send_json({"job_id": job_id, "status": "queued"}, status=202)
            return
        if parsed.path == "/api/report-workbench":
            body = _json_body(self)
            profile = _normalize_profile(body)
            store = _load_profile_store()
            store["last_profile"] = profile
            _save_profile_store(store)
            job_id = _JOB_STORE.submit(lambda _p=profile: _run_workbench(_p), job_type="workbench")
            self._send_json({"job_id": job_id, "status": "queued"}, status=202)
            return
        if parsed.path == "/api/report-workbench/rerun-last":
            store = _load_profile_store()
            profile = _normalize_profile(store.get("last_profile", {}))
            store["last_profile"] = profile
            _save_profile_store(store)
            job_id = _JOB_STORE.submit(lambda _p=profile: _run_workbench(_p), job_type="workbench")
            self._send_json({"job_id": job_id, "status": "queued"}, status=202)
            return
        if parsed.path == "/api/workbench-profiles/save":
            body = _json_body(self)
            name = str(body.get("name", "")).strip()
            if not name:
                self._send_json({"error": "preset name is required"}, status=400)
                return
            profile = _normalize_profile(body.get("profile", {}))
            store = _load_profile_store()
            store["presets"][name] = profile
            store["last_profile"] = profile
            _save_profile_store(store)
            self._send_json({"status": "ok", "store": store})
            return
        if parsed.path == "/api/workbench-profiles/delete":
            body = _json_body(self)
            name = str(body.get("name", "")).strip()
            if not name:
                self._send_json({"error": "preset name is required"}, status=400)
                return
            store = _load_profile_store()
            store["presets"].pop(name, None)
            _save_profile_store(store)
            self._send_json({"status": "ok", "store": store})
            return
        if parsed.path == "/api/write-situation-analysis":
            body = _json_body(self)
            ts = subprocess.run(
                [sys.executable, "-c", "from datetime import datetime, UTC; print(datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ'))"],
                text=True, capture_output=True, cwd=ROOT, check=False,
            ).stdout.strip()
            out_path = REPORTS_DIR / f"situation-analysis-{ts}.md"
            # Normalise list params to comma-separated strings
            raw_countries = body.get("countries", "Madagascar,Mozambique")
            if isinstance(raw_countries, list):
                raw_countries = ",".join(raw_countries)
            raw_dtypes = body.get("disaster_types", "cyclone/storm,flood")
            if isinstance(raw_dtypes, list):
                raw_dtypes = ",".join(raw_dtypes)
            cmd = [
                "write-situation-analysis",
                "--countries",
                str(raw_countries),
                "--disaster-types",
                str(raw_dtypes),
                "--title",
                str(body.get("title", "Situation Analysis")),
                "--event-name",
                str(body.get("event_name", "")),
                "--event-type",
                str(body.get("event_type", "")),
                "--period",
                str(body.get("period", "")),
                "--sa-template",
                str(body.get("sa_template", "config/report_template.situation_analysis.json")),
                "--limit-cycles",
                str(int(body.get("limit_cycles", 20))),
                "--limit-events",
                str(int(body.get("limit_events", 80))),
                "--output",
                str(out_path),
            ]
            max_age = body.get("max_age_days")
            if max_age is not None:
                cmd.extend(["--max-age-days", str(int(max_age))])
            if bool(body.get("use_llm", False)):
                cmd.append("--use-llm")
            if bool(body.get("quality_gate", False)):
                cmd.append("--quality-gate")
            def _run_sa(_cmd=cmd, _out=out_path) -> dict[str, Any]:
                result = _run_cli(_cmd, timeout=600)
                if _out.exists():
                    result["markdown"] = _out.read_text(encoding="utf-8")
                else:
                    result.setdefault("markdown", "")
                result["output_file"] = _out.name
                return result
            job_id = _JOB_STORE.submit(
                _run_sa,
                job_type="sa",
                llm=bool(body.get("use_llm", False)),
            )
            self._send_json({"job_id": job_id, "status": "queued"}, status=202)
            return
        if parsed.path == "/api/run-pipeline":
            body = _json_body(self)
            raw_countries = body.get("countries", "Madagascar,Mozambique")
            if isinstance(raw_countries, list):
                raw_countries = ",".join(raw_countries)
            raw_dtypes = body.get("disaster_types", "cyclone/storm,flood")
            if isinstance(raw_dtypes, list):
                raw_dtypes = ",".join(raw_dtypes)
            cmd = [
                "run-pipeline",
                "--countries",
                str(raw_countries),
                "--disaster-types",
                str(raw_dtypes),
                "--report-title",
                str(body.get("report_title", "Disaster Intelligence Report")),
                "--sa-title",
                str(body.get("sa_title", "Situation Analysis")),
                "--event-name",
                str(body.get("event_name", "")),
                "--event-type",
                str(body.get("event_type", "")),
                "--period",
                str(body.get("period", "")),
                "--limit-cycles",
                str(int(body.get("limit_cycles", 20))),
                "--limit-events",
                str(int(body.get("limit_events", 80))),
            ]
            max_age = body.get("max_age_days")
            if max_age is not None:
                cmd.extend(["--max-age-days", str(int(max_age))])
            if bool(body.get("use_llm", False)):
                cmd.append("--use-llm")
            job_id = _JOB_STORE.submit(
                lambda _c=cmd: _run_cli(_c, timeout=900),
                exclusive=True,
                job_type="pipeline",
                llm=bool(body.get("use_llm", False)),
            )
            self._send_json({"job_id": job_id, "status": "queued"}, status=202)
            return
        self._send_json({"error": "not found"}, status=404)


def _port_free(host: str, port: int) -> bool:
    """Return True if the port is available to bind."""
    import socket as _socket
    probe = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    probe.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 0)
    try:
        probe.bind((host, port))
        probe.close()
        return True
    except OSError:
        probe.close()
        return False


def _run_legacy(host: str, port: int) -> int:
    """Start the legacy ThreadingHTTPServer (Phase A, no FastAPI dependency)."""
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(json.dumps({"status": "listening", "host": host, "port": port, "mode": "legacy"}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _run_fastapi(host: str, port: int) -> int:
    """Start the FastAPI + uvicorn server (Phase B — direct calls, async jobs)."""
    import uvicorn  # type: ignore[import]
    from agent_hum_crawler.api.app import create_app

    app = create_app()
    print(json.dumps({"status": "listening", "host": host, "port": port, "mode": "fastapi"}), flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Moltis Dashboard API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument(
        "--mode",
        choices=["auto", "fastapi", "legacy"],
        default="auto",
        help=(
            "Server backend: 'fastapi' requires fastapi+uvicorn installed; "
            "'legacy' uses stdlib http.server; 'auto' (default) prefers fastapi."
        ),
    )
    args = parser.parse_args()

    if not _port_free(args.host, args.port):
        print(
            json.dumps({
                "status": "error",
                "error": f"Port {args.port} already in use — kill the existing server first.",
            }),
            flush=True,
        )
        return 1

    use_fastapi = False
    if args.mode == "fastapi":
        use_fastapi = True
    elif args.mode == "auto":
        try:
            import uvicorn  # noqa: F401
            import fastapi  # noqa: F401
            use_fastapi = True
        except ImportError:
            use_fastapi = False

    if use_fastapi:
        return _run_fastapi(args.host, args.port)
    return _run_legacy(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())

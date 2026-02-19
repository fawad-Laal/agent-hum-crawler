"""Minimal local API for the crawler dashboard.

Exposes existing CLI functionality for a lightweight React frontend.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
E2E_DIR = ROOT / "artifacts" / "e2e"


def _json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


def _run_cli(args: list[str]) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "agent_hum_crawler.main", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "status": "error",
            "command": args,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "command": args, "stdout": proc.stdout, "stderr": proc.stderr}


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


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AHCDashboard/1.0"

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
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return
        if parsed.path == "/api/overview":
            quality = _run_cli(["quality-report", "--limit", "10"])
            source_health = _run_cli(["source-health", "--limit", "10"])
            hardening = _run_cli(["hardening-gate", "--limit", "10"])
            cycles = _run_cli(["show-cycles", "--limit", "20"])
            e2e_summary = _latest_e2e_summary()
            quality_trend = _quality_trend(window=10)
            payload = {
                "quality": quality,
                "source_health": source_health,
                "hardening": hardening,
                "cycles": cycles if isinstance(cycles, list) else [],
                "quality_trend": quality_trend,
                "latest_e2e_summary": e2e_summary,
            }
            self._send_json(payload)
            return
        if parsed.path == "/api/reports":
            self._send_json({"reports": _list_reports()})
            return
        if parsed.path.startswith("/api/reports/"):
            name = parsed.path.split("/api/reports/", 1)[1]
            report_path = _safe_report_path(name)
            if not report_path:
                self._send_json({"error": "report not found"}, status=404)
                return
            self._send_json({"name": report_path.name, "markdown": report_path.read_text(encoding="utf-8")})
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
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
                "--include-content",
            ]
            self._send_json(_run_cli(cmd))
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
                "--report-template",
                str(body.get("report_template", "config/report_template.brief.json")),
                "--enforce-report-quality",
            ]
            if bool(body.get("use_llm", False)):
                cmd.append("--use-llm")
            self._send_json(_run_cli(cmd))
            return
        if parsed.path == "/api/report-workbench":
            body = _json_body(self)
            countries = str(body.get("countries", "Madagascar,Mozambique"))
            disaster_types = str(body.get("disaster_types", "cyclone/storm,flood"))
            limit_cycles = int(body.get("limit_cycles", 20))
            limit_events = int(body.get("limit_events", 30))
            template_path = str(body.get("report_template", "config/report_template.brief.json"))
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
                template_path=template_path,
                use_llm=False,
            )
            ai = _build_workbench_report(
                countries=countries,
                disaster_types=disaster_types,
                limit_cycles=limit_cycles,
                limit_events=limit_events,
                template_path=template_path,
                use_llm=True,
            )

            payload = {
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
            self._send_json(payload)
            return
        self._send_json({"error": "not found"}, status=404)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(json.dumps({"status": "listening", "host": args.host, "port": args.port}))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

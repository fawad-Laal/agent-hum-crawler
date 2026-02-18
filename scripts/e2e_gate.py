"""Deterministic E2E regression gate with artifact capture."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def run_and_capture(command: list[str], output_path: Path) -> dict:
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    output_path.write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        err_path = output_path.with_suffix(".stderr.log")
        err_path.write_text(proc.stderr, encoding="utf-8")
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(command)}; "
            f"stdout={output_path}; stderr={err_path}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON output from {' '.join(command)} at {output_path}") from exc


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-root", default="artifacts/e2e")
    args = parser.parse_args(argv)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.artifacts_root) / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    replay = run_and_capture(
        [
            sys.executable,
            "-m",
            "agent_hum_crawler.main",
            "replay-fixture",
            "--fixture",
            "tests/fixtures/replay_pakistan_flood_quake.json",
        ],
        out_dir / "01_replay_fixture.json",
    )
    ensure(int(replay.get("event_count", 0)) >= 1, "Replay fixture produced no events")
    ensure("alerts_contract" in replay, "Replay fixture missing alerts_contract")

    quality = run_and_capture(
        [sys.executable, "-m", "agent_hum_crawler.main", "quality-report", "--limit", "5"],
        out_dir / "02_quality_report.json",
    )
    ensure("cycles_analyzed" in quality, "quality-report missing cycles_analyzed")

    source_health = run_and_capture(
        [sys.executable, "-m", "agent_hum_crawler.main", "source-health", "--limit", "5"],
        out_dir / "03_source_health.json",
    )
    ensure("cycles_analyzed" in source_health, "source-health missing cycles_analyzed")

    hardening = run_and_capture(
        [sys.executable, "-m", "agent_hum_crawler.main", "hardening-gate", "--limit", "5"],
        out_dir / "04_hardening_gate.json",
    )
    ensure("status" in hardening, "hardening-gate missing status")

    conformance = run_and_capture(
        [
            sys.executable,
            "-m",
            "agent_hum_crawler.main",
            "conformance-report",
            "--limit",
            "5",
            "--streaming-event-lifecycle",
            "pass",
            "--tool-registry-source-metadata",
            "pass",
            "--mcp-disable-builtin-fallback",
            "pass",
            "--auth-matrix-local-remote-proxy",
            "pass",
            "--proxy-hardening-configuration",
            "pass",
        ],
        out_dir / "05_conformance_report.json",
    )
    ensure("moltis_conformance" in conformance, "conformance-report missing moltis_conformance")

    summary = {
        "status": "pass",
        "timestamp_utc": ts,
        "artifacts_dir": str(out_dir),
        "checks": {
            "replay_event_count": replay.get("event_count", 0),
            "hardening_status": hardening.get("status"),
            "conformance_status": conformance.get("moltis_conformance", {}).get("status"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

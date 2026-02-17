"""CLI entrypoint for intake, collection, persistence, and scheduling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .config import RuntimeConfig
from .cycle import run_cycle_once
from .alerts import build_alert_contract
from .database import build_quality_report, get_recent_cycles, init_db
from .intake import run_intake
from .scheduler import SchedulerOptions, start_scheduler
from .settings import is_reliefweb_enabled, load_environment
from .state import RuntimeState, load_state, save_state


def default_config_path() -> Path:
    return Path.home() / ".moltis" / "agent-hum-crawler" / "runtime_config.json"


def save_runtime_config(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_runtime_config(path: Path | None = None) -> RuntimeConfig:
    file_path = path or default_config_path()
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return RuntimeConfig.model_validate(payload)


def build_runtime_config_from_args(args: argparse.Namespace) -> RuntimeConfig:
    countries = [c.strip() for c in (args.countries or "").split(",") if c.strip()]
    disaster_types = [d.strip() for d in (args.disaster_types or "").split(",") if d.strip()]
    local_news_feeds = getattr(args, "local_news_feeds", "") or ""
    interval = args.interval
    if getattr(args, "use_saved_config", False):
        interval = load_runtime_config().check_interval_minutes
    return RuntimeConfig(
        countries=countries,
        disaster_types=disaster_types,
        check_interval_minutes=interval,
        priority_sources=[u.strip() for u in local_news_feeds.split(",") if u.strip()],
    )


def _update_state(summary: str) -> Path:
    state = load_state()
    if not isinstance(state, RuntimeState):
        state = RuntimeState()
    state.touch()
    state.last_summary = summary
    return save_state(state)


def _resolve_config(args: argparse.Namespace) -> RuntimeConfig:
    return load_runtime_config() if args.use_saved_config else build_runtime_config_from_args(args)


def cmd_intake(_: argparse.Namespace) -> int:
    try:
        config = run_intake()
    except ValueError as exc:
        print(f"Setup aborted: {exc}")
        return 1

    config_path = default_config_path()
    save_runtime_config(config_path, config.model_dump())
    state_path = _update_state("Configured runtime via intake")
    print("Saved runtime config:", config_path)
    print("Saved runtime state:", state_path)
    return 0


def cmd_fetch_reliefweb(args: argparse.Namespace) -> int:
    load_environment()
    if not is_reliefweb_enabled():
        print("ReliefWeb is disabled via RELIEFWEB_ENABLED=false")
        return 0

    config = _resolve_config(args)

    try:
        result = run_cycle_once(config=config, limit=args.limit, include_content=args.include_content)
    except Exception as exc:  # pragma: no cover
        print(f"ReliefWeb fetch failed: {exc}")
        return 1

    payload = {
        "cycle_id": result.cycle_id,
        "summary": result.summary,
        "connector_count": result.connector_count,
        "raw_item_count": result.raw_item_count,
        "event_count": result.event_count,
        "events": [e.model_dump(mode="json") for e in result.events if e.connector == "reliefweb"],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_run_cycle(args: argparse.Namespace) -> int:
    load_environment()
    init_db()

    config = _resolve_config(args)

    result = run_cycle_once(config=config, limit=args.limit, include_content=args.include_content)
    alert_contract = build_alert_contract(result.events, interval_minutes=config.check_interval_minutes)
    payload = {
        "cycle_id": result.cycle_id,
        "summary": result.summary,
        "connector_count": result.connector_count,
        "raw_item_count": result.raw_item_count,
        "event_count": result.event_count,
        "alerts_contract": alert_contract,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_start_scheduler(args: argparse.Namespace) -> int:
    load_environment()
    init_db()

    config = _resolve_config(args)
    interval = config.check_interval_minutes

    def run_once() -> None:
        result = run_cycle_once(config=config, limit=args.limit, include_content=args.include_content)
        alert_contract = build_alert_contract(result.events, interval_minutes=interval)
        print(
            json.dumps(
                {
                    "cycle_id": result.cycle_id,
                    "summary": result.summary,
                    "event_count": result.event_count,
                    "critical_high_count": len(alert_contract["critical_high_alerts"]),
                    "medium_updates_count": len(alert_contract["medium_updates"]),
                },
                ensure_ascii=False,
            )
        )

    start_scheduler(
        run_cycle=run_once,
        options=SchedulerOptions(interval_minutes=interval, max_runs=args.max_runs),
    )
    return 0


def cmd_show_cycles(args: argparse.Namespace) -> int:
    cycles = get_recent_cycles(limit=args.limit)
    print(json.dumps([c.model_dump() for c in cycles], indent=2, ensure_ascii=False))
    return 0


def cmd_quality_report(args: argparse.Namespace) -> int:
    report = build_quality_report(limit_cycles=args.limit)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-hum-crawler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    intake_parser = subparsers.add_parser("intake", help="Run interactive runtime intake")
    intake_parser.set_defaults(func=cmd_intake)

    fetch_parser = subparsers.add_parser("fetch-reliefweb", help="Fetch and normalize ReliefWeb items")
    fetch_parser.add_argument("--countries", help="Comma-separated country list")
    fetch_parser.add_argument("--disaster-types", help="Comma-separated disaster types")
    fetch_parser.add_argument("--interval", type=int, default=30, help="Interval minutes for config validation")
    fetch_parser.add_argument("--limit", type=int, default=20, help="Max ReliefWeb items to fetch")
    fetch_parser.add_argument("--include-content", action="store_true", help="Fetch content-level text")
    fetch_parser.add_argument("--use-saved-config", action="store_true", help="Use saved runtime config")
    fetch_parser.set_defaults(func=cmd_fetch_reliefweb)

    run_parser = subparsers.add_parser("run-cycle", help="Run one full collection + dedupe + persistence cycle")
    run_parser.add_argument("--countries", help="Comma-separated country list")
    run_parser.add_argument("--disaster-types", help="Comma-separated disaster types")
    run_parser.add_argument("--interval", type=int, default=30, help="Interval minutes for config validation")
    run_parser.add_argument("--limit", type=int, default=15, help="Max items per connector")
    run_parser.add_argument("--include-content", action="store_true", help="Fetch content-level text")
    run_parser.add_argument("--local-news-feeds", help="Comma-separated local news RSS/Atom feed URLs")
    run_parser.add_argument("--use-saved-config", action="store_true", help="Use saved runtime config")
    run_parser.set_defaults(func=cmd_run_cycle)

    scheduler_parser = subparsers.add_parser("start-scheduler", help="Run monitoring cycles on interval")
    scheduler_parser.add_argument("--countries", help="Comma-separated country list")
    scheduler_parser.add_argument("--disaster-types", help="Comma-separated disaster types")
    scheduler_parser.add_argument("--interval", type=int, default=30, help="Interval minutes for config validation")
    scheduler_parser.add_argument("--limit", type=int, default=15, help="Max items per connector")
    scheduler_parser.add_argument("--include-content", action="store_true", help="Fetch content-level text")
    scheduler_parser.add_argument("--local-news-feeds", help="Comma-separated local news RSS/Atom feed URLs")
    scheduler_parser.add_argument("--use-saved-config", action="store_true", help="Use saved runtime config")
    scheduler_parser.add_argument("--max-runs", type=int, default=None, help="Stop after N cycles (for testing)")
    scheduler_parser.set_defaults(func=cmd_start_scheduler)

    cycles_parser = subparsers.add_parser("show-cycles", help="Show recent persisted cycles")
    cycles_parser.add_argument("--limit", type=int, default=10)
    cycles_parser.set_defaults(func=cmd_show_cycles)

    quality_parser = subparsers.add_parser(
        "quality-report",
        help="Show quality metrics from recent persisted cycles",
    )
    quality_parser.add_argument("--limit", type=int, default=10)
    quality_parser.set_defaults(func=cmd_quality_report)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

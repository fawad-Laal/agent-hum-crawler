"""CLI entrypoint for intake, collection, persistence, and scheduling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .config import RuntimeConfig
from .conformance import evaluate_moltis_conformance
from .cycle import run_cycle_once, run_source_check
from .feature_flags import get_feature_flag
from .alerts import build_alert_contract
from .database import build_quality_report, build_source_health_report, get_recent_cycles, init_db
from .hardening import evaluate_hardening_gate, evaluate_llm_quality_gate
from .intake import run_intake
from .pilot import run_pilot
from .scheduler import SchedulerOptions, start_scheduler
from .settings import is_reliefweb_enabled, load_environment
from .replay import run_replay_fixture
from .reporting import (
    build_graph_context,
    evaluate_report_quality,
    load_report_template,
    render_long_form_report,
    write_report_file,
)
from .coordinator import PipelineCoordinator
from .situation_analysis import write_situation_analysis
from .state import RuntimeState, load_state, reset_state, save_state


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
        max_item_age_days=getattr(args, "max_age_days", None),
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
    warnings: list[str] = []
    for metric in result.connector_metrics:
        for w in metric.get("warnings", []) or []:
            if isinstance(w, str) and w.strip():
                warnings.append(w.strip())
    payload = {
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
                    "llm_enriched_count": int(result.llm_enrichment.get("enriched_count", 0)),
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


def cmd_llm_report(args: argparse.Namespace) -> int:
    quality = build_quality_report(limit_cycles=args.limit)
    report = evaluate_llm_quality_gate(
        quality,
        min_llm_enrichment_rate=args.min_llm_enrichment_rate,
        min_citation_coverage_rate=args.min_citation_coverage_rate,
        enforce_llm_quality=args.enforce_llm_quality,
    )
    payload = {
        "quality_report": quality,
        "llm_quality_gate": report,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_source_health(args: argparse.Namespace) -> int:
    report = build_source_health_report(limit_cycles=args.limit)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_source_check(args: argparse.Namespace) -> int:
    load_environment()
    config = _resolve_config(args)
    report = run_source_check(config=config, limit=args.limit, include_content=args.include_content)
    warnings: list[str] = []
    for metric in report.connector_metrics:
        for w in metric.get("warnings", []) or []:
            if isinstance(w, str) and w.strip():
                warnings.append(w.strip())
    payload = {
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
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_replay_fixture(args: argparse.Namespace) -> int:
    result = run_replay_fixture(args.fixture)
    payload = {
        "summary": result.summary,
        "event_count": len(result.events),
        "events": [e.model_dump(mode="json") for e in result.events],
        "current_hashes": result.current_hashes,
        "alerts_contract": result.alerts_contract,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_hardening_gate(args: argparse.Namespace) -> int:
    quality = build_quality_report(limit_cycles=args.limit)
    source_health = build_source_health_report(limit_cycles=args.limit)
    report = evaluate_hardening_gate(
        quality,
        source_health,
        max_duplicate_rate=args.max_duplicate_rate,
        min_traceable_rate=args.min_traceable_rate,
        max_connector_failure_rate=args.max_connector_failure_rate,
        min_llm_enrichment_rate=args.min_llm_enrichment_rate,
        min_citation_coverage_rate=args.min_citation_coverage_rate,
        enforce_llm_quality=args.enforce_llm_quality,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_pilot_run(args: argparse.Namespace) -> int:
    load_environment()
    init_db()
    if args.reset_state_before_run:
        reset_path = reset_state()
        print(f'{{"state_reset": true, "state_path": "{reset_path}"}}')
    config = _resolve_config(args)
    report = run_pilot(
        config=config,
        cycles=args.cycles,
        limit=args.limit,
        include_content=args.include_content,
        sleep_seconds=args.sleep_seconds,
        max_duplicate_rate=args.max_duplicate_rate,
        min_traceable_rate=args.min_traceable_rate,
        max_connector_failure_rate=args.max_connector_failure_rate,
        min_llm_enrichment_rate=args.min_llm_enrichment_rate,
        min_citation_coverage_rate=args.min_citation_coverage_rate,
        enforce_llm_quality=args.enforce_llm_quality,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_conformance_report(args: argparse.Namespace) -> int:
    quality = build_quality_report(limit_cycles=args.limit)
    source_health = build_source_health_report(limit_cycles=args.limit)
    gate = evaluate_hardening_gate(
        quality,
        source_health,
        max_duplicate_rate=args.max_duplicate_rate,
        min_traceable_rate=args.min_traceable_rate,
        max_connector_failure_rate=args.max_connector_failure_rate,
        min_llm_enrichment_rate=args.min_llm_enrichment_rate,
        min_citation_coverage_rate=args.min_citation_coverage_rate,
        enforce_llm_quality=args.enforce_llm_quality,
    )
    conformance = evaluate_moltis_conformance(
        hardening_status=str(gate.get("status", "warning")),
        checks={
            "streaming_event_lifecycle": args.streaming_event_lifecycle,
            "tool_registry_source_metadata": args.tool_registry_source_metadata,
            "mcp_disable_builtin_fallback": args.mcp_disable_builtin_fallback,
            "auth_matrix_local_remote_proxy": args.auth_matrix_local_remote_proxy,
            "proxy_hardening_configuration": args.proxy_hardening_configuration,
        },
    )
    payload = {
        "hardening_gate": gate,
        "moltis_conformance": conformance,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_write_report(args: argparse.Namespace) -> int:
    load_environment()
    template_path = Path(args.report_template) if args.report_template else None
    template = load_report_template(template_path)
    sections = template.get("sections", {})
    required_sections = [
        str(sections.get("executive_summary", "Executive Summary")),
        str(sections.get("incident_highlights", "Incident Highlights")),
        str(sections.get("source_reliability", "Source and Connector Reliability Snapshot")),
        str(sections.get("risk_outlook", "Risk Outlook")),
        str(sections.get("method", "Method")),
    ]
    countries = [c.strip() for c in (args.countries or "").split(",") if c.strip()]
    disaster_types = [d.strip() for d in (args.disaster_types or "").split(",") if d.strip()]
    strict_filters = args.strict_filters
    if strict_filters is None:
        strict_filters = bool(get_feature_flag("report_strict_filters_default", True))

    graph_context = build_graph_context(
        countries=countries,
        disaster_types=disaster_types,
        limit_cycles=args.limit_cycles,
        limit_events=args.limit_events,
        strict_filters=strict_filters,
        max_age_days=args.max_age_days,
        country_min_events=args.country_min_events,
        max_per_connector=args.max_per_connector,
        max_per_source=args.max_per_source,
    )
    report = render_long_form_report(
        graph_context=graph_context,
        title=args.title,
        use_llm=args.use_llm,
        template_path=template_path,
    )
    llm_used = "AI Assisted: Yes" in report
    quality = evaluate_report_quality(
        report_markdown=report,
        min_citation_density=args.min_citation_density,
        required_sections=required_sections,
    )
    out = write_report_file(report_markdown=report, output_path=Path(args.output) if args.output else None)
    payload = {
        "status": "ok" if quality.get("status") == "pass" or not args.enforce_report_quality else "fail",
        "report_path": str(out),
        "meta": graph_context.get("meta", {}),
        "llm_used": llm_used,
        "report_quality": quality,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.enforce_report_quality and quality.get("status") != "pass":
        return 1
    return 0


def cmd_write_situation_analysis(args: argparse.Namespace) -> int:
    load_environment()
    countries = [c.strip() for c in (args.countries or "").split(",") if c.strip()]
    disaster_types = [d.strip() for d in (args.disaster_types or "").split(",") if d.strip()]
    admin_hierarchy: dict[str, list[str]] | None = None
    if args.admin_hierarchy:
        try:
            admin_hierarchy = json.loads(Path(args.admin_hierarchy).read_text(encoding="utf-8"))
        except Exception as exc:
            print(json.dumps({"status": "error", "message": f"Failed to load admin hierarchy: {exc}"}))
            return 1
    template_path = Path(args.sa_template) if args.sa_template else None
    result = write_situation_analysis(
        countries=countries,
        disaster_types=disaster_types,
        title=args.title,
        event_name=args.event_name,
        event_type=args.event_type,
        period=args.period,
        admin_hierarchy=admin_hierarchy,
        template_path=template_path,
        use_llm=args.use_llm,
        limit_cycles=args.limit_cycles,
        limit_events=args.limit_events,
        max_age_days=args.max_age_days,
        output_path=Path(args.output) if args.output else None,
        quality_gate=getattr(args, "quality_gate", False),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_run_pipeline(args: argparse.Namespace) -> int:
    """Run the full coordinated pipeline: evidence → ontology → report + SA."""
    load_environment()
    countries = [c.strip() for c in (args.countries or "").split(",") if c.strip()]
    disaster_types = [d.strip() for d in (args.disaster_types or "").split(",") if d.strip()]
    strict_filters = args.strict_filters
    if strict_filters is None:
        strict_filters = bool(get_feature_flag("report_strict_filters_default", True))
    admin_hierarchy: dict[str, list[str]] | None = None
    if args.admin_hierarchy:
        try:
            admin_hierarchy = json.loads(Path(args.admin_hierarchy).read_text(encoding="utf-8"))
        except Exception as exc:
            print(json.dumps({"status": "error", "message": f"Failed to load admin hierarchy: {exc}"}))
            return 1

    coord = PipelineCoordinator(
        countries=countries,
        disaster_types=disaster_types,
        limit_cycles=args.limit_cycles,
        limit_events=args.limit_events,
        max_age_days=args.max_age_days,
        strict_filters=strict_filters,
        country_min_events=args.country_min_events,
        max_per_connector=args.max_per_connector,
        max_per_source=args.max_per_source,
    )

    report_template_path = Path(args.report_template) if args.report_template else None
    sa_template_path = Path(args.sa_template) if args.sa_template else None

    ctx = coord.run_pipeline(
        report_title=args.report_title,
        report_template_path=report_template_path,
        sa_title=args.sa_title,
        event_name=args.event_name,
        event_type=args.event_type,
        period=args.period,
        admin_hierarchy=admin_hierarchy,
        sa_template_path=sa_template_path,
        use_llm=args.use_llm,
        write_files=True,
    )

    payload = coord.summary_dict()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
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
    fetch_parser.add_argument("--max-age-days", type=int, help="Only include items published within N days")
    fetch_parser.set_defaults(func=cmd_fetch_reliefweb)

    run_parser = subparsers.add_parser("run-cycle", help="Run one full collection + dedupe + persistence cycle")
    run_parser.add_argument("--countries", help="Comma-separated country list")
    run_parser.add_argument("--disaster-types", help="Comma-separated disaster types")
    run_parser.add_argument("--interval", type=int, default=30, help="Interval minutes for config validation")
    run_parser.add_argument("--limit", type=int, default=15, help="Max items per connector")
    run_parser.add_argument("--include-content", action="store_true", help="Fetch content-level text")
    run_parser.add_argument("--local-news-feeds", help="Comma-separated local news RSS/Atom feed URLs")
    run_parser.add_argument("--use-saved-config", action="store_true", help="Use saved runtime config")
    run_parser.add_argument("--max-age-days", type=int, help="Only include items published within N days")
    run_parser.set_defaults(func=cmd_run_cycle)

    scheduler_parser = subparsers.add_parser("start-scheduler", help="Run monitoring cycles on interval")
    scheduler_parser.add_argument("--countries", help="Comma-separated country list")
    scheduler_parser.add_argument("--disaster-types", help="Comma-separated disaster types")
    scheduler_parser.add_argument("--interval", type=int, default=30, help="Interval minutes for config validation")
    scheduler_parser.add_argument("--limit", type=int, default=15, help="Max items per connector")
    scheduler_parser.add_argument("--include-content", action="store_true", help="Fetch content-level text")
    scheduler_parser.add_argument("--local-news-feeds", help="Comma-separated local news RSS/Atom feed URLs")
    scheduler_parser.add_argument("--use-saved-config", action="store_true", help="Use saved runtime config")
    scheduler_parser.add_argument("--max-age-days", type=int, help="Only include items published within N days")
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

    llm_parser = subparsers.add_parser(
        "llm-report",
        help="Show LLM enrichment quality metrics and LLM quality gate status",
    )
    llm_parser.add_argument("--limit", type=int, default=10)
    llm_parser.add_argument("--min-llm-enrichment-rate", type=float, default=0.10)
    llm_parser.add_argument("--min-citation-coverage-rate", type=float, default=0.95)
    llm_parser.add_argument("--enforce-llm-quality", action="store_true")
    llm_parser.set_defaults(func=cmd_llm_report)

    source_health_parser = subparsers.add_parser(
        "source-health",
        help="Show connector/feed health and failure analytics",
    )
    source_health_parser.add_argument("--limit", type=int, default=10)
    source_health_parser.set_defaults(func=cmd_source_health)

    source_check_parser = subparsers.add_parser(
        "source-check",
        help="Run one-by-one source connectivity/data checks without persistence side effects",
    )
    source_check_parser.add_argument("--countries", help="Comma-separated country list")
    source_check_parser.add_argument("--disaster-types", help="Comma-separated disaster types")
    source_check_parser.add_argument("--interval", type=int, default=30, help="Interval minutes for config validation")
    source_check_parser.add_argument("--limit", type=int, default=20, help="Max items per source check")
    source_check_parser.add_argument("--include-content", action="store_true", help="Fetch content-level text")
    source_check_parser.add_argument("--local-news-feeds", help="Comma-separated local news RSS/Atom feed URLs")
    source_check_parser.add_argument("--use-saved-config", action="store_true", help="Use saved runtime config")
    source_check_parser.add_argument("--max-age-days", type=int, help="Only include items published within N days")
    source_check_parser.set_defaults(func=cmd_source_check)

    replay_parser = subparsers.add_parser(
        "replay-fixture",
        help="Run a fixture-based replay cycle for QA/hardening",
    )
    replay_parser.add_argument("--fixture", required=True, help="Path to replay fixture JSON")
    replay_parser.set_defaults(func=cmd_replay_fixture)

    gate_parser = subparsers.add_parser(
        "hardening-gate",
        help="Evaluate hardening thresholds from recent cycle metrics",
    )
    gate_parser.add_argument("--limit", type=int, default=10)
    gate_parser.add_argument("--max-duplicate-rate", type=float, default=0.10)
    gate_parser.add_argument("--min-traceable-rate", type=float, default=0.95)
    gate_parser.add_argument("--max-connector-failure-rate", type=float, default=0.60)
    gate_parser.add_argument("--min-llm-enrichment-rate", type=float, default=0.10)
    gate_parser.add_argument("--min-citation-coverage-rate", type=float, default=0.95)
    gate_parser.add_argument("--enforce-llm-quality", action="store_true")
    gate_parser.set_defaults(func=cmd_hardening_gate)

    pilot_parser = subparsers.add_parser(
        "pilot-run",
        help="Run N consecutive cycles and return quality/source-health/hardening evidence",
    )
    pilot_parser.add_argument("--countries", help="Comma-separated country list")
    pilot_parser.add_argument("--disaster-types", help="Comma-separated disaster types")
    pilot_parser.add_argument("--interval", type=int, default=30, help="Interval minutes for config validation")
    pilot_parser.add_argument("--limit", type=int, default=15, help="Max items per connector")
    pilot_parser.add_argument("--include-content", action="store_true", help="Fetch content-level text")
    pilot_parser.add_argument("--local-news-feeds", help="Comma-separated local news RSS/Atom feed URLs")
    pilot_parser.add_argument("--use-saved-config", action="store_true", help="Use saved runtime config")
    pilot_parser.add_argument("--cycles", type=int, default=7, help="Number of consecutive cycles to run")
    pilot_parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Delay between cycles")
    pilot_parser.add_argument("--max-duplicate-rate", type=float, default=0.10)
    pilot_parser.add_argument("--min-traceable-rate", type=float, default=0.95)
    pilot_parser.add_argument("--max-connector-failure-rate", type=float, default=0.60)
    pilot_parser.add_argument("--min-llm-enrichment-rate", type=float, default=0.10)
    pilot_parser.add_argument("--min-citation-coverage-rate", type=float, default=0.95)
    pilot_parser.add_argument("--enforce-llm-quality", action="store_true")
    pilot_parser.add_argument("--max-age-days", type=int, help="Only include items published within N days")
    pilot_parser.add_argument(
        "--reset-state-before-run",
        action="store_true",
        help="Reset runtime hash state before pilot window for reproducible non-zero sampling",
    )
    pilot_parser.set_defaults(func=cmd_pilot_run)

    conformance_parser = subparsers.add_parser(
        "conformance-report",
        help="Combine hardening gate with Moltis conformance checks",
    )
    conformance_parser.add_argument("--limit", type=int, default=10)
    conformance_parser.add_argument("--max-duplicate-rate", type=float, default=0.10)
    conformance_parser.add_argument("--min-traceable-rate", type=float, default=0.95)
    conformance_parser.add_argument("--max-connector-failure-rate", type=float, default=0.60)
    conformance_parser.add_argument("--min-llm-enrichment-rate", type=float, default=0.10)
    conformance_parser.add_argument("--min-citation-coverage-rate", type=float, default=0.95)
    conformance_parser.add_argument("--enforce-llm-quality", action="store_true")
    conformance_parser.add_argument(
        "--streaming-event-lifecycle",
        choices=["pass", "fail", "pending"],
        default="pending",
    )
    conformance_parser.add_argument(
        "--tool-registry-source-metadata",
        choices=["pass", "fail", "pending"],
        default="pending",
    )
    conformance_parser.add_argument(
        "--mcp-disable-builtin-fallback",
        choices=["pass", "fail", "pending"],
        default="pending",
    )
    conformance_parser.add_argument(
        "--auth-matrix-local-remote-proxy",
        choices=["pass", "fail", "pending"],
        default="pending",
    )
    conformance_parser.add_argument(
        "--proxy-hardening-configuration",
        choices=["pass", "fail", "pending"],
        default="pending",
    )
    conformance_parser.set_defaults(func=cmd_conformance_report)

    report_parser = subparsers.add_parser(
        "write-report",
        help="Generate long-form GraphRAG report from persisted monitoring database",
    )
    report_parser.add_argument("--countries", help="Comma-separated country filters")
    report_parser.add_argument("--disaster-types", help="Comma-separated disaster type filters")
    report_parser.add_argument("--limit-cycles", type=int, default=20)
    report_parser.add_argument("--limit-events", type=int, default=60)
    report_parser.add_argument(
        "--strict-filters",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="When true, do not fallback to cross-filter evidence if selected filters return zero events.",
    )
    report_parser.add_argument("--title", default="Disaster Intelligence Report")
    report_parser.add_argument("--use-llm", action="store_true", help="Use optional LLM final drafting")
    report_parser.add_argument(
        "--report-template",
        default="config/report_template.json",
        help="Path to JSON report template (sections + length limits)",
    )
    report_parser.add_argument("--output", help="Write markdown report to this path")
    report_parser.add_argument("--max-age-days", type=int, help="Only include events published within N days")
    report_parser.add_argument(
        "--country-min-events",
        type=int,
        default=1,
        help="Minimum events per requested country when available (0 disables balancing).",
    )
    report_parser.add_argument(
        "--max-per-connector",
        type=int,
        default=8,
        help="Maximum selected incidents from a single connector (0 disables cap).",
    )
    report_parser.add_argument(
        "--max-per-source",
        type=int,
        default=4,
        help="Maximum selected incidents from a single source label/domain (0 disables cap).",
    )
    report_parser.add_argument("--min-citation-density", type=float, default=0.005)
    report_parser.add_argument("--enforce-report-quality", action="store_true")
    report_parser.set_defaults(func=cmd_write_report)

    sa_parser = subparsers.add_parser(
        "write-situation-analysis",
        help="Generate OCHA-style Situation Analysis from persisted monitoring database",
    )
    sa_parser.add_argument("--countries", help="Comma-separated country filters")
    sa_parser.add_argument("--disaster-types", help="Comma-separated disaster type filters")
    sa_parser.add_argument("--title", default="Situation Analysis")
    sa_parser.add_argument("--event-name", default="", help="Event name, e.g. 'Tropical Cyclone Gezani-26'")
    sa_parser.add_argument("--event-type", default="", help="Event type, e.g. 'Cyclone/storm'")
    sa_parser.add_argument("--period", default="", help="Event period, e.g. '2-6 March 2026'")
    sa_parser.add_argument(
        "--admin-hierarchy",
        help="Path to JSON file mapping admin1 → [admin2] districts",
    )
    sa_parser.add_argument(
        "--sa-template",
        default="config/report_template.situation_analysis.json",
        help="Path to Situation Analysis JSON template",
    )
    sa_parser.add_argument("--use-llm", action="store_true", help="Use LLM for narrative sections")
    sa_parser.add_argument("--limit-cycles", type=int, default=20)
    sa_parser.add_argument("--limit-events", type=int, default=80)
    sa_parser.add_argument("--max-age-days", type=int, help="Only include events published within N days")
    sa_parser.add_argument("--output", help="Write markdown report to this path")
    sa_parser.add_argument("--quality-gate", action="store_true", help="Run SA quality gate scoring")
    sa_parser.set_defaults(func=cmd_write_situation_analysis)

    # ── run-pipeline (coordinated report + SA) ───────────────────────
    pipe_parser = subparsers.add_parser(
        "run-pipeline",
        help="Run full coordinated pipeline: evidence → ontology → report + SA",
    )
    pipe_parser.add_argument("--countries", help="Comma-separated country filters")
    pipe_parser.add_argument("--disaster-types", help="Comma-separated disaster type filters")
    pipe_parser.add_argument("--report-title", default="Disaster Intelligence Report")
    pipe_parser.add_argument("--sa-title", default="Situation Analysis")
    pipe_parser.add_argument("--event-name", default="", help="Event name, e.g. 'Tropical Cyclone Gezani-26'")
    pipe_parser.add_argument("--event-type", default="", help="Event type, e.g. 'Cyclone/storm'")
    pipe_parser.add_argument("--period", default="", help="Event period, e.g. '2-6 March 2026'")
    pipe_parser.add_argument("--admin-hierarchy", help="Path to JSON file mapping admin1 → [admin2] districts")
    pipe_parser.add_argument("--report-template", help="Path to report template JSON")
    pipe_parser.add_argument(
        "--sa-template",
        default="config/report_template.situation_analysis.json",
        help="Path to SA template JSON",
    )
    pipe_parser.add_argument("--use-llm", action="store_true", help="Use LLM for narrative sections")
    pipe_parser.add_argument("--limit-cycles", type=int, default=20)
    pipe_parser.add_argument("--limit-events", type=int, default=80)
    pipe_parser.add_argument("--max-age-days", type=int, help="Only include events published within N days")
    pipe_parser.add_argument(
        "--strict-filters", type=lambda x: None if x is None else x.lower() == "true",
        default=None,
        help="Enforce strict country/disaster filters (default: from feature flags)",
    )
    pipe_parser.add_argument("--country-min-events", type=int, default=1)
    pipe_parser.add_argument("--max-per-connector", type=int, default=8)
    pipe_parser.add_argument("--max-per-source", type=int, default=4)
    pipe_parser.set_defaults(func=cmd_run_pipeline)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

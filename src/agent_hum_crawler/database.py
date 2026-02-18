"""SQLite persistence layer for cycle outputs using SQLModel."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from sqlmodel import Field, Session, SQLModel, create_engine, select

from .models import ProcessedEvent, RawSourceItem


class CycleRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_at: str = Field(index=True)
    connector_count: int
    raw_item_count: int
    event_count: int
    summary: str = ""
    llm_enabled: bool = False
    llm_attempted_count: int = 0
    llm_enriched_count: int = 0
    llm_fallback_count: int = 0
    llm_provider_error_count: int = 0
    llm_validation_fail_count: int = 0
    llm_insufficient_text_count: int = 0


class EventRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(index=True)
    event_id: str = Field(index=True)
    status: str
    connector: str
    source_type: str
    title: str
    url: str
    country: str
    disaster_type: str
    published_at: str | None = None
    severity: str
    confidence: str
    summary: str
    llm_enriched: bool = False
    citations_json: str = "[]"
    corroboration_sources: int = 1
    corroboration_connectors: int = 1
    corroboration_source_types: int = 1


class RawItemRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(index=True)
    connector: str
    source_type: str
    title: str
    url: str
    published_at: str | None = None
    payload_json: str


class ConnectorHealthRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(index=True)
    connector: str = Field(index=True)
    attempted_sources: int
    healthy_sources: int
    failed_sources: int
    fetched_count: int
    matched_count: int
    errors_json: str = "[]"


class FeedHealthRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(index=True)
    connector: str = Field(index=True)
    source_name: str
    source_url: str
    status: str
    error: str = ""
    fetched_count: int = 0
    matched_count: int = 0


def default_db_path() -> Path:
    return Path.home() / ".moltis" / "agent-hum-crawler" / "monitoring.db"


def build_engine(path: Path | None = None):
    db_path = path or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}")


def init_db(path: Path | None = None) -> None:
    engine = build_engine(path)
    SQLModel.metadata.create_all(engine)
    _ensure_cyclerun_columns(engine)
    _ensure_eventrecord_columns(engine)


def _ensure_eventrecord_columns(engine) -> None:
    required = {
        "corroboration_sources": "INTEGER NOT NULL DEFAULT 1",
        "corroboration_connectors": "INTEGER NOT NULL DEFAULT 1",
        "corroboration_source_types": "INTEGER NOT NULL DEFAULT 1",
        "llm_enriched": "INTEGER NOT NULL DEFAULT 0",
        "citations_json": "TEXT NOT NULL DEFAULT '[]'",
    }

    with engine.connect() as conn:
        existing = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(eventrecord)").fetchall()
        }
        for column, column_type in required.items():
            if column not in existing:
                conn.exec_driver_sql(
                    f"ALTER TABLE eventrecord ADD COLUMN {column} {column_type}"
                )


def _ensure_cyclerun_columns(engine) -> None:
    required = {
        "llm_enabled": "INTEGER NOT NULL DEFAULT 0",
        "llm_attempted_count": "INTEGER NOT NULL DEFAULT 0",
        "llm_enriched_count": "INTEGER NOT NULL DEFAULT 0",
        "llm_fallback_count": "INTEGER NOT NULL DEFAULT 0",
        "llm_provider_error_count": "INTEGER NOT NULL DEFAULT 0",
        "llm_validation_fail_count": "INTEGER NOT NULL DEFAULT 0",
        "llm_insufficient_text_count": "INTEGER NOT NULL DEFAULT 0",
    }

    with engine.connect() as conn:
        existing = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(cyclerun)").fetchall()
        }
        for column, column_type in required.items():
            if column not in existing:
                conn.exec_driver_sql(
                    f"ALTER TABLE cyclerun ADD COLUMN {column} {column_type}"
                )


def persist_cycle(
    raw_items: List[RawSourceItem],
    events: List[ProcessedEvent],
    connector_count: int,
    summary: str,
    connector_metrics: list[dict] | None = None,
    llm_stats: dict | None = None,
    path: Path | None = None,
) -> int:
    engine = build_engine(path)
    SQLModel.metadata.create_all(engine)
    _ensure_cyclerun_columns(engine)
    _ensure_eventrecord_columns(engine)
    llm_stats = llm_stats or {}

    now = datetime.now(timezone.utc).isoformat()
    cycle = CycleRun(
        run_at=now,
        connector_count=connector_count,
        raw_item_count=len(raw_items),
        event_count=len(events),
        summary=summary,
        llm_enabled=bool(llm_stats.get("enabled", False)),
        llm_attempted_count=int(llm_stats.get("attempted_count", 0)),
        llm_enriched_count=int(llm_stats.get("enriched_count", 0)),
        llm_fallback_count=int(llm_stats.get("fallback_count", 0)),
        llm_provider_error_count=int(llm_stats.get("provider_error_count", 0)),
        llm_validation_fail_count=int(llm_stats.get("validation_fail_count", 0)),
        llm_insufficient_text_count=int(llm_stats.get("insufficient_text_count", 0)),
    )

    with Session(engine) as session:
        session.add(cycle)
        session.commit()
        session.refresh(cycle)
        cycle_id = int(cycle.id or 0)

        for event in events:
            session.add(
                EventRecord(
                    cycle_id=cycle_id,
                    event_id=event.event_id,
                    status=event.status,
                    connector=event.connector,
                    source_type=event.source_type,
                    title=event.title,
                    url=str(event.url),
                    country=event.country,
                    disaster_type=event.disaster_type,
                    published_at=event.published_at,
                    severity=event.severity,
                    confidence=event.confidence,
                    summary=event.summary,
                    llm_enriched=event.llm_enriched,
                    citations_json=json.dumps([c.model_dump(mode="json") for c in event.citations]),
                    corroboration_sources=event.corroboration_sources,
                    corroboration_connectors=event.corroboration_connectors,
                    corroboration_source_types=event.corroboration_source_types,
                )
            )

        for raw_item in raw_items:
            session.add(
                RawItemRecord(
                    cycle_id=cycle_id,
                    connector=raw_item.connector,
                    source_type=raw_item.source_type,
                    title=raw_item.title,
                    url=str(raw_item.url),
                    published_at=raw_item.published_at,
                    payload_json=json.dumps(raw_item.model_dump(mode="json")),
                )
            )

        for metric in connector_metrics or []:
            connector = str(metric.get("connector", "unknown"))
            session.add(
                ConnectorHealthRecord(
                    cycle_id=cycle_id,
                    connector=connector,
                    attempted_sources=int(metric.get("attempted_sources", 0)),
                    healthy_sources=int(metric.get("healthy_sources", 0)),
                    failed_sources=int(metric.get("failed_sources", 0)),
                    fetched_count=int(metric.get("fetched_count", 0)),
                    matched_count=int(metric.get("matched_count", 0)),
                    errors_json=json.dumps(metric.get("errors", [])),
                )
            )

            for source in metric.get("source_results", []) or []:
                session.add(
                    FeedHealthRecord(
                        cycle_id=cycle_id,
                        connector=connector,
                        source_name=str(source.get("source_name", "")),
                        source_url=str(source.get("source_url", "")),
                        status=str(source.get("status", "unknown")),
                        error=str(source.get("error", "")),
                        fetched_count=int(source.get("fetched_count", 0)),
                        matched_count=int(source.get("matched_count", 0)),
                    )
                )

        session.commit()

    return cycle_id


def get_recent_cycles(limit: int = 10, path: Path | None = None) -> list[CycleRun]:
    engine = build_engine(path)
    SQLModel.metadata.create_all(engine)
    _ensure_cyclerun_columns(engine)
    with Session(engine) as session:
        statement = select(CycleRun).order_by(CycleRun.id.desc()).limit(limit)
        return list(session.exec(statement))


def build_quality_report(limit_cycles: int = 10, path: Path | None = None) -> dict:
    engine = build_engine(path)
    try:
        _ensure_cyclerun_columns(engine)
        _ensure_eventrecord_columns(engine)
    except Exception:
        return {
            "cycles_analyzed": 0,
            "events_analyzed": 0,
            "duplicate_rate_estimate": 0.0,
            "traceable_rate": 0.0,
            "high_critical_count": 0,
            "high_confidence_high_critical_count": 0,
            "llm_enriched_events": 0,
            "llm_enrichment_rate": 0.0,
            "citation_coverage_rate": 0.0,
            "llm_provider_error_count": 0,
            "llm_validation_fail_count": 0,
        }

    with Session(engine) as session:
        cycles = list(session.exec(select(CycleRun).order_by(CycleRun.id.desc()).limit(limit_cycles)))
        if not cycles:
            return {
                "cycles_analyzed": 0,
                "events_analyzed": 0,
                "duplicate_rate_estimate": 0.0,
                "traceable_rate": 0.0,
                "high_critical_count": 0,
                "high_confidence_high_critical_count": 0,
                "llm_enriched_events": 0,
                "llm_enrichment_rate": 0.0,
                "citation_coverage_rate": 0.0,
                "llm_provider_error_count": 0,
                "llm_validation_fail_count": 0,
            }

        cycle_ids = [c.id for c in cycles if c.id is not None]
        events = list(session.exec(select(EventRecord).where(EventRecord.cycle_id.in_(cycle_ids))))

        total = len(events)
        if total == 0:
            return {
                "cycles_analyzed": len(cycles),
                "events_analyzed": 0,
                "duplicate_rate_estimate": 0.0,
                "traceable_rate": 1.0,
                "high_critical_count": 0,
                "high_confidence_high_critical_count": 0,
                "llm_enriched_events": 0,
                "llm_enrichment_rate": 0.0,
                "citation_coverage_rate": 0.0,
                "llm_provider_error_count": 0,
                "llm_validation_fail_count": 0,
            }

        unchanged = sum(1 for e in events if e.status == "unchanged")
        traceable = sum(1 for e in events if bool(e.url and e.published_at))
        llm_enriched = sum(1 for e in events if bool(e.llm_enriched))
        cited = sum(
            1
            for e in events
            if bool(e.citations_json and e.citations_json != "[]" and e.citations_json != "null")
        )
        high_critical = [e for e in events if e.severity in {"high", "critical"}]
        high_conf_high_critical = sum(1 for e in high_critical if e.confidence == "high")
        llm_provider_errors = sum(int(c.llm_provider_error_count) for c in cycles)
        llm_validation_failures = sum(int(c.llm_validation_fail_count) for c in cycles)

        return {
            "cycles_analyzed": len(cycles),
            "events_analyzed": total,
            "duplicate_rate_estimate": round(unchanged / total, 4),
            "traceable_rate": round(traceable / total, 4),
            "high_critical_count": len(high_critical),
            "high_confidence_high_critical_count": high_conf_high_critical,
            "llm_attempted_events": sum(int(c.llm_attempted_count) for c in cycles),
            "llm_enriched_events": llm_enriched,
            "llm_fallback_events": sum(int(c.llm_fallback_count) for c in cycles),
            "llm_insufficient_text_events": sum(int(c.llm_insufficient_text_count) for c in cycles),
            "llm_enrichment_rate": round(llm_enriched / total, 4),
            "citation_coverage_rate": round(cited / total, 4),
            "llm_provider_error_count": llm_provider_errors,
            "llm_validation_fail_count": llm_validation_failures,
        }


def build_source_health_report(limit_cycles: int = 10, path: Path | None = None) -> dict:
    engine = build_engine(path)

    with Session(engine) as session:
        try:
            cycles = list(session.exec(select(CycleRun).order_by(CycleRun.id.desc()).limit(limit_cycles)))
        except Exception:
            return {"cycles_analyzed": 0, "connectors": [], "sources": []}
        if not cycles:
            return {"cycles_analyzed": 0, "connectors": [], "sources": []}

        cycle_ids = [c.id for c in cycles if c.id is not None]
        try:
            connector_rows = list(
                session.exec(
                    select(ConnectorHealthRecord).where(ConnectorHealthRecord.cycle_id.in_(cycle_ids))
                )
            )
            source_rows = list(
                session.exec(
                    select(FeedHealthRecord).where(FeedHealthRecord.cycle_id.in_(cycle_ids))
                )
            )
        except Exception:
            return {"cycles_analyzed": len(cycles), "connectors": [], "sources": []}

        connector_agg: dict[str, dict] = {}
        for row in connector_rows:
            bucket = connector_agg.setdefault(
                row.connector,
                {
                    "connector": row.connector,
                    "runs": 0,
                    "attempted_sources": 0,
                    "healthy_sources": 0,
                    "failed_sources": 0,
                    "fetched_count": 0,
                    "matched_count": 0,
                },
            )
            bucket["runs"] += 1
            bucket["attempted_sources"] += row.attempted_sources
            bucket["healthy_sources"] += row.healthy_sources
            bucket["failed_sources"] += row.failed_sources
            bucket["fetched_count"] += row.fetched_count
            bucket["matched_count"] += row.matched_count

        connectors = []
        for bucket in connector_agg.values():
            attempted = bucket["attempted_sources"] or 1
            bucket["failure_rate"] = round(bucket["failed_sources"] / attempted, 4)
            bucket["match_rate"] = round(bucket["matched_count"] / max(1, bucket["fetched_count"]), 4)
            connectors.append(bucket)
        connectors.sort(key=lambda x: x["failure_rate"], reverse=True)

        source_agg: dict[tuple[str, str], dict] = {}
        for row in source_rows:
            key = (row.connector, row.source_url)
            bucket = source_agg.setdefault(
                key,
                {
                    "connector": row.connector,
                    "source_name": row.source_name,
                    "source_url": row.source_url,
                    "runs": 0,
                    "failed_runs": 0,
                    "fetched_count": 0,
                    "matched_count": 0,
                    "last_error": "",
                },
            )
            bucket["runs"] += 1
            if row.status != "ok":
                bucket["failed_runs"] += 1
                if row.error:
                    bucket["last_error"] = row.error
            bucket["fetched_count"] += row.fetched_count
            bucket["matched_count"] += row.matched_count

        sources = []
        for bucket in source_agg.values():
            bucket["failure_rate"] = round(bucket["failed_runs"] / max(1, bucket["runs"]), 4)
            bucket["match_rate"] = round(bucket["matched_count"] / max(1, bucket["fetched_count"]), 4)
            sources.append(bucket)
        sources.sort(key=lambda x: (x["failure_rate"], -x["match_rate"]), reverse=True)

        return {
            "cycles_analyzed": len(cycles),
            "connectors": connectors,
            "sources": sources,
        }

"""SQLite persistence layer for cycle outputs using SQLModel."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

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
    canonical_url: str | None = None
    country: str
    country_iso3: str = ""
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
    canonical_url: str | None = None
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


# ── Ontology persistence tables (Phase 4) ───────────────────────────


class OntologySnapshot(SQLModel, table=True):
    """One snapshot of the ontology graph, tied to a pipeline run."""
    id: int | None = Field(default=None, primary_key=True)
    created_at: str = Field(index=True)
    evidence_count: int = 0
    impact_count: int = 0
    need_count: int = 0
    risk_count: int = 0
    response_count: int = 0
    geo_count: int = 0


class ImpactRecord(SQLModel, table=True):
    """Persisted ImpactObservation."""
    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(index=True)
    description: str = ""
    impact_type: str = ""
    geo_area: str = ""
    admin_level: int = 0
    severity_phase: int = 2
    figures_json: str = "{}"
    source_url: str = ""
    source_connector: str = ""
    confidence: str = "medium"
    reported_date: str = ""
    source_label: str = ""
    credibility_tier: int = 4


class NeedRecord(SQLModel, table=True):
    """Persisted NeedStatement."""
    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(index=True)
    description: str = ""
    need_type: str = ""
    geo_area: str = ""
    admin_level: int = 0
    severity_phase: int = 2
    indicates_impact: str = ""
    source_url: str = ""
    reported_date: str = ""
    source_label: str = ""


class RiskRecord(SQLModel, table=True):
    """Persisted RiskStatement."""
    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(index=True)
    description: str = ""
    hazard_name: str = ""
    geo_area: str = ""
    horizon: str = "48h"
    probability: str = "likely"
    source_url: str = ""
    reported_date: str = ""
    source_label: str = ""


class ResponseRecord(SQLModel, table=True):
    """Persisted ResponseActivity."""
    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(index=True)
    description: str = ""
    actor: str = ""
    actor_type: str = ""
    geo_area: str = ""
    sector: str = ""
    source_url: str = ""


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
    _ensure_rawitem_columns(engine)
    _ensure_ontology_tables(engine)


def _ensure_eventrecord_columns(engine) -> None:
    required = {
        "corroboration_sources": "INTEGER NOT NULL DEFAULT 1",
        "corroboration_connectors": "INTEGER NOT NULL DEFAULT 1",
        "corroboration_source_types": "INTEGER NOT NULL DEFAULT 1",
        "llm_enriched": "INTEGER NOT NULL DEFAULT 0",
        "citations_json": "TEXT NOT NULL DEFAULT '[]'",
        "canonical_url": "TEXT",
        "country_iso3": "TEXT NOT NULL DEFAULT ''",
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


def _ensure_rawitem_columns(engine) -> None:
    required = {
        "canonical_url": "TEXT",
    }
    with engine.connect() as conn:
        existing = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(rawitemrecord)").fetchall()
        }
        for column, column_type in required.items():
            if column not in existing:
                conn.exec_driver_sql(
                    f"ALTER TABLE rawitemrecord ADD COLUMN {column} {column_type}"
                )


def _ensure_ontology_tables(engine) -> None:
    """Create ontology tables if they don't exist yet."""
    # SQLModel.metadata.create_all will handle new tables that aren't yet in the DB.
    # This is safe to call repeatedly.
    SQLModel.metadata.create_all(engine)


# ── Ontology Persistence (Phase 4) ──────────────────────────────────


def persist_ontology(engine: Any, ontology: Any) -> dict[str, int]:
    """Persist a ``HumanitarianOntologyGraph`` into the database.

    Creates a new ``OntologySnapshot`` row and bulk-inserts all impact,
    need, risk, and response records.

    Returns a counts dict: ``{impacts, needs, risks, responses}``.
    """
    SQLModel.metadata.create_all(engine)

    now = datetime.now(timezone.utc).isoformat()
    snapshot = OntologySnapshot(
        created_at=now,
        evidence_count=len(ontology.claims),
        impact_count=len(ontology.impacts),
        need_count=len(ontology.needs),
        risk_count=len(ontology.risks),
        response_count=len(ontology.responses),
        geo_count=len(ontology.geo_areas),
    )

    with Session(engine) as session:
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)
        snap_id = int(snapshot.id or 0)

        for imp in ontology.impacts:
            session.add(ImpactRecord(
                snapshot_id=snap_id,
                description=imp.description[:500],
                impact_type=imp.impact_type.value if hasattr(imp.impact_type, "value") else str(imp.impact_type),
                geo_area=imp.geo_area,
                admin_level=imp.admin_level,
                severity_phase=imp.severity_phase,
                figures_json=json.dumps(imp.figures),
                source_url=imp.source_url,
                source_connector=imp.source_connector,
                confidence=imp.confidence,
                reported_date=imp.reported_date,
                source_label=imp.source_label,
                credibility_tier=imp.credibility_tier,
            ))

        for need in ontology.needs:
            session.add(NeedRecord(
                snapshot_id=snap_id,
                description=need.description[:500],
                need_type=need.need_type.value if hasattr(need.need_type, "value") else str(need.need_type),
                geo_area=need.geo_area,
                admin_level=need.admin_level,
                severity_phase=need.severity_phase,
                indicates_impact=need.indicates_impact,
                source_url=need.source_url,
                reported_date=need.reported_date,
                source_label=need.source_label,
            ))

        for risk in ontology.risks:
            session.add(RiskRecord(
                snapshot_id=snap_id,
                description=risk.description[:500],
                hazard_name=risk.hazard_name,
                geo_area=risk.geo_area,
                horizon=risk.horizon,
                probability=risk.probability,
                source_url=risk.source_url,
                reported_date=risk.reported_date,
                source_label=risk.source_label,
            ))

        for resp in ontology.responses:
            session.add(ResponseRecord(
                snapshot_id=snap_id,
                description=resp.description[:500],
                actor=resp.actor,
                actor_type=resp.actor_type,
                geo_area=resp.geo_area,
                sector=resp.sector,
                source_url=resp.source_url,
            ))

        session.commit()

    return {
        "snapshot_id": snap_id,
        "impacts": len(ontology.impacts),
        "needs": len(ontology.needs),
        "risks": len(ontology.risks),
        "responses": len(ontology.responses),
    }


def get_ontology_snapshots(
    limit: int = 10, engine: Any | None = None, path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return recent ontology snapshots as dicts for trending."""
    if engine is None:
        engine = build_engine(path)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        rows = list(
            session.exec(
                select(OntologySnapshot).order_by(OntologySnapshot.id.desc()).limit(limit)
            )
        )
        return [
            {
                "id": r.id,
                "created_at": r.created_at,
                "evidence_count": r.evidence_count,
                "impact_count": r.impact_count,
                "need_count": r.need_count,
                "risk_count": r.risk_count,
                "response_count": r.response_count,
                "geo_count": r.geo_count,
            }
            for r in rows
        ]


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
    _ensure_rawitem_columns(engine)
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
                    canonical_url=str(event.canonical_url) if event.canonical_url else None,
                    country=event.country,
                    country_iso3=event.country_iso3,
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
                    canonical_url=str(raw_item.canonical_url) if raw_item.canonical_url else None,
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
    _ensure_eventrecord_columns(engine)
    _ensure_rawitem_columns(engine)
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
            if row.status in {"failed", "error"}:
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

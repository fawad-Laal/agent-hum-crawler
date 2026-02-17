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


def default_db_path() -> Path:
    return Path.home() / ".moltis" / "agent-hum-crawler" / "monitoring.db"


def build_engine(path: Path | None = None):
    db_path = path or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}")


def init_db(path: Path | None = None) -> None:
    engine = build_engine(path)
    SQLModel.metadata.create_all(engine)
    _ensure_eventrecord_columns(engine)


def _ensure_eventrecord_columns(engine) -> None:
    required = {
        "corroboration_sources": "INTEGER NOT NULL DEFAULT 1",
        "corroboration_connectors": "INTEGER NOT NULL DEFAULT 1",
        "corroboration_source_types": "INTEGER NOT NULL DEFAULT 1",
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


def persist_cycle(
    raw_items: List[RawSourceItem],
    events: List[ProcessedEvent],
    connector_count: int,
    summary: str,
    path: Path | None = None,
) -> int:
    engine = build_engine(path)
    SQLModel.metadata.create_all(engine)
    _ensure_eventrecord_columns(engine)

    now = datetime.now(timezone.utc).isoformat()
    cycle = CycleRun(
        run_at=now,
        connector_count=connector_count,
        raw_item_count=len(raw_items),
        event_count=len(events),
        summary=summary,
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

        session.commit()

    return cycle_id


def get_recent_cycles(limit: int = 10, path: Path | None = None) -> list[CycleRun]:
    engine = build_engine(path)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        statement = select(CycleRun).order_by(CycleRun.id.desc()).limit(limit)
        return list(session.exec(statement))


def build_quality_report(limit_cycles: int = 10, path: Path | None = None) -> dict:
    engine = build_engine(path)
    SQLModel.metadata.create_all(engine)
    _ensure_eventrecord_columns(engine)

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
            }

        unchanged = sum(1 for e in events if e.status == "unchanged")
        traceable = sum(1 for e in events if bool(e.url and e.published_at))
        high_critical = [e for e in events if e.severity in {"high", "critical"}]
        high_conf_high_critical = sum(1 for e in high_critical if e.confidence == "high")

        return {
            "cycles_analyzed": len(cycles),
            "events_analyzed": total,
            "duplicate_rate_estimate": round(unchanged / total, 4),
            "traceable_rate": round(traceable / total, 4),
            "high_critical_count": len(high_critical),
            "high_confidence_high_critical_count": high_conf_high_critical,
        }

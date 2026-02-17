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


def persist_cycle(
    raw_items: List[RawSourceItem],
    events: List[ProcessedEvent],
    connector_count: int,
    summary: str,
    path: Path | None = None,
) -> int:
    engine = build_engine(path)
    SQLModel.metadata.create_all(engine)

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

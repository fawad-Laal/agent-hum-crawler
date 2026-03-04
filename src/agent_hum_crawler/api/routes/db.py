"""GET /api/db/* — raw monitoring-database read endpoints.

All queries are read-only (opened with ``?mode=ro`` URI flag).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────


def _db_path() -> Path:
    return Path.home() / ".moltis" / "agent-hum-crawler" / "monitoring.db"


def _query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    db = _db_path()
    if not db.exists():
        return []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# ── routes ────────────────────────────────────────────────────────────────


@router.get("/db/cycles")
def db_cycles(limit: int = Query(50, ge=1, le=200)) -> dict:
    rows = _query(
        "SELECT * FROM cyclerun ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return {"cycles": rows, "count": len(rows), "db_path": str(_db_path())}


@router.get("/db/events")
def db_events(
    limit: int = Query(100, ge=1, le=500),
    country: str | None = None,
    disaster_type: str | None = None,
) -> dict:
    where_parts: list[str] = []
    params: list[Any] = []
    if country:
        where_parts.append("country = ?")
        params.append(country)
    if disaster_type:
        where_parts.append("disaster_type LIKE ?")
        params.append(f"%{disaster_type}%")
    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    rows = _query(
        f"SELECT * FROM eventrecord {where} ORDER BY id DESC LIMIT ?",
        tuple(params) + (limit,),
    )
    return {"events": rows, "count": len(rows)}


@router.get("/db/raw-items")
def db_raw_items(limit: int = Query(100, ge=1, le=500)) -> dict:
    rows = _query(
        "SELECT id, cycle_id, connector, source_type, title, url, published_at "
        "FROM rawitemrecord ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return {"raw_items": rows, "count": len(rows)}


@router.get("/db/feed-health")
def db_feed_health(limit: int = Query(100, ge=1, le=500)) -> dict:
    rows = _query(
        "SELECT * FROM feedhealthrecord ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return {"feed_health": rows, "count": len(rows)}

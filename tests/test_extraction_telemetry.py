"""Tests for Phase 9.3 — Extraction telemetry model.

Covers:
  - ExtractionEvent model validation
  - persist_cycle writing ExtractionRecord rows
  - get_extraction_records filtering by cycle_id
"""

from pathlib import Path

import pytest
from sqlmodel import Session, select

from agent_hum_crawler.database import (
    ExtractionRecord,
    build_engine,
    get_extraction_records,
    init_db,
    persist_cycle,
)
from agent_hum_crawler.models import ExtractionEvent, ProcessedEvent, RawSourceItem


# ── helpers ──────────────────────────────────────────────────────────


def _make_raw_item(
    url: str = "https://example.org/item1",
    extraction_events: list[ExtractionEvent] | None = None,
) -> RawSourceItem:
    return RawSourceItem(
        connector="reliefweb",
        source_type="humanitarian",
        url=url,
        title="Test item",
        published_at="2026-03-04",
        country_candidates=["Lebanon"],
        text="Some field text",
        language="en",
        extraction_events=extraction_events or [],
    )


def _make_event(url: str = "https://example.org/item1") -> ProcessedEvent:
    return ProcessedEvent(
        event_id="ev-001",
        status="new",
        connector="reliefweb",
        source_type="humanitarian",
        url=url,
        title="Test event",
        country="Lebanon",
        disaster_type="conflict",
        published_at="2026-03-04",
        severity="medium",
        confidence="medium",
        summary="Test summary",
    )


# ── tests ─────────────────────────────────────────────────────────────


class TestExtractionEventModel:
    def test_valid_ok_status(self) -> None:
        ev = ExtractionEvent(
            attachment_url="https://example.org/doc.pdf",
            connector="reliefweb",
            downloaded=True,
            status="ok",
            method="pdfplumber",
            char_count=1500,
            duration_ms=320,
        )
        assert ev.status == "ok"
        assert ev.char_count == 1500
        assert ev.duration_ms == 320
        assert ev.error == ""

    def test_defaults(self) -> None:
        ev = ExtractionEvent(
            attachment_url="https://example.org/doc.pdf",
            connector="reliefweb",
            status="skipped",
            method="none",
        )
        assert ev.downloaded is False
        assert ev.char_count == 0
        assert ev.duration_ms == 0
        assert ev.error == ""

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(Exception):
            ExtractionEvent(
                attachment_url="https://example.org/doc.pdf",
                connector="reliefweb",
                status="unknown_status",  # not in Literal
                method="none",
            )


class TestPersistCycleWritesExtractionRecords:
    def test_extraction_records_written(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)

        ev1 = ExtractionEvent(
            attachment_url="https://reliefweb.int/files/report.pdf",
            connector="reliefweb",
            downloaded=True,
            status="ok",
            method="pdfplumber",
            char_count=2400,
            duration_ms=450,
        )
        ev2 = ExtractionEvent(
            attachment_url="https://reliefweb.int/files/annex.pdf",
            connector="reliefweb",
            downloaded=True,
            status="empty",
            method="pypdf",
            char_count=0,
            duration_ms=120,
        )
        raw = [_make_raw_item(extraction_events=[ev1, ev2])]
        events = [_make_event()]

        cycle_id = persist_cycle(
            raw_items=raw,
            events=events,
            connector_count=1,
            summary="ok",
            path=db_path,
        )
        assert cycle_id > 0

        engine = build_engine(db_path)
        with Session(engine) as session:
            rows = session.exec(select(ExtractionRecord)).all()

        assert len(rows) == 2
        ok_rows = [r for r in rows if r.status == "ok"]
        empty_rows = [r for r in rows if r.status == "empty"]
        assert len(ok_rows) == 1
        assert len(empty_rows) == 1
        assert ok_rows[0].char_count == 2400
        assert ok_rows[0].duration_ms == 450
        assert ok_rows[0].method == "pdfplumber"
        assert ok_rows[0].cycle_id == cycle_id

    def test_payload_json_excludes_extraction_events(self, tmp_path: Path) -> None:
        """extraction_events must not be serialised into RawItemRecord.payload_json."""
        from agent_hum_crawler.database import RawItemRecord
        from sqlmodel import Session, select

        db_path = tmp_path / "monitoring.db"
        init_db(db_path)

        ev = ExtractionEvent(
            attachment_url="https://reliefweb.int/files/rep.pdf",
            connector="reliefweb",
            downloaded=True,
            status="ok",
            method="pdfplumber",
            char_count=100,
            duration_ms=50,
        )
        raw = [_make_raw_item(extraction_events=[ev])]

        persist_cycle(
            raw_items=raw,
            events=[],
            connector_count=1,
            summary="ok",
            path=db_path,
        )

        engine = build_engine(db_path)
        with Session(engine) as session:
            record = session.exec(select(RawItemRecord)).first()

        import json

        payload = json.loads(record.payload_json)
        assert "extraction_events" not in payload


class TestGetExtractionRecordsFilters:
    def test_filter_by_cycle_id(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)

        ev_a = ExtractionEvent(
            attachment_url="https://rw.int/a.pdf",
            connector="reliefweb",
            downloaded=True,
            status="ok",
            method="pdfplumber",
            char_count=500,
            duration_ms=100,
        )
        ev_b = ExtractionEvent(
            attachment_url="https://rw.int/b.pdf",
            connector="reliefweb",
            downloaded=True,
            status="failed",
            method="none",
            char_count=0,
            duration_ms=20,
            error="http 404",
        )

        cycle_id_1 = persist_cycle(
            raw_items=[_make_raw_item(url="https://rw.int/1", extraction_events=[ev_a])],
            events=[],
            connector_count=1,
            summary="cycle1",
            path=db_path,
        )
        cycle_id_2 = persist_cycle(
            raw_items=[_make_raw_item(url="https://rw.int/2", extraction_events=[ev_b])],
            events=[],
            connector_count=1,
            summary="cycle2",
            path=db_path,
        )

        records_1 = get_extraction_records(cycle_id=cycle_id_1, path=db_path)
        records_2 = get_extraction_records(cycle_id=cycle_id_2, path=db_path)

        assert len(records_1) == 1
        assert records_1[0]["status"] == "ok"
        assert records_1[0]["cycle_id"] == cycle_id_1

        assert len(records_2) == 1
        assert records_2[0]["status"] == "failed"
        assert records_2[0]["error"] == "http 404"

    def test_filter_by_status(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)

        events = [
            ExtractionEvent(
                attachment_url=f"https://rw.int/{i}.pdf",
                connector="reliefweb",
                downloaded=True,
                status=s,
                method="pdfplumber" if s == "ok" else "none",
                char_count=100 if s == "ok" else 0,
                duration_ms=50,
            )
            for i, s in enumerate(["ok", "ok", "empty", "failed"])
        ]
        persist_cycle(
            raw_items=[_make_raw_item(extraction_events=events)],
            events=[],
            connector_count=1,
            summary="mixed",
            path=db_path,
        )

        ok_records = get_extraction_records(status="ok", path=db_path)
        failed_records = get_extraction_records(status="failed", path=db_path)

        assert len(ok_records) == 2
        assert len(failed_records) == 1

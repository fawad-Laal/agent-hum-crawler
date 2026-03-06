"""Tests for Phase 9.4 — extraction diagnostics report API and CLI (R27, R28)."""
from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session

from agent_hum_crawler.database import (
    CycleRun,
    ExtractionRecord,
    build_engine,
    build_extraction_diagnostics_report,
    init_db,
)


# ────────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────────

def _seed_cycle(db_path: Path, *, is_ok: bool = True) -> int:
    """Insert a CycleRun and return its id."""
    engine = build_engine(db_path)
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        run = CycleRun(
            run_at="2026-03-04T10:00:00Z",
            summary="ok" if is_ok else "error",
            connector_count=1,
            raw_item_count=5,
            event_count=2,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id  # type: ignore[return-value]


def _seed_extraction(
    db_path: Path,
    cycle_id: int,
    *,
    connector: str = "reliefweb",
    status: str = "ok",
    method: str = "pdfplumber",
    char_count: int = 1200,
    duration_ms: int = 450,
    error: str = "",
    attachment_url: str = "https://example.org/doc.pdf",
    source_url: str = "https://example.org/item1",
) -> None:
    """Insert one ExtractionRecord row via a direct Session call."""
    engine = build_engine(db_path)
    with Session(engine) as session:
        session.add(
            ExtractionRecord(
                cycle_id=cycle_id,
                connector=connector,
                source_url=source_url,
                attachment_url=attachment_url,
                downloaded=status != "skipped",
                status=status,
                method=method,
                char_count=char_count,
                duration_ms=duration_ms,
                error=error,
                created_at="2026-03-04T10:00:30Z",
            )
        )
        session.commit()


# ────────────────────────────────────────────────────────────────────
# TestBuildExtractionDiagnosticsReport
# ────────────────────────────────────────────────────────────────────

class TestBuildExtractionDiagnosticsReport:
    """Unit tests for build_extraction_diagnostics_report()."""

    def test_empty_db_returns_zero_totals(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        report = build_extraction_diagnostics_report(limit_cycles=10, path=db_path)
        assert report["total_records"] == 0
        assert report["by_status"] == {}
        assert report["by_connector"] == []
        assert report["by_method"] == []
        assert report["top_errors"] == []
        assert report["low_yield_connectors"] == []

    def test_aggregates_by_status(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        # 3 ok, 2 failed, 1 skipped
        for _ in range(3):
            _seed_extraction(db_path, cid, status="ok")
        for _ in range(2):
            _seed_extraction(db_path, cid, status="failed", error="timeout", method="pdfplumber")
        _seed_extraction(db_path, cid, status="skipped", method="none")

        report = build_extraction_diagnostics_report(limit_cycles=5, path=db_path)
        assert report["total_records"] == 6
        assert report["by_status"]["ok"] == 3
        assert report["by_status"]["failed"] == 2
        assert report["by_status"]["skipped"] == 1

    def test_by_connector_ok_rate_computed(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        # reliefweb: 3 ok, 0 failed → ok_rate 1.0
        for _ in range(3):
            _seed_extraction(db_path, cid, connector="reliefweb", status="ok")
        # rss_feeds: 1 ok, 4 failed → ok_rate 0.2
        _seed_extraction(db_path, cid, connector="rss_feeds", status="ok")
        for _ in range(4):
            _seed_extraction(db_path, cid, connector="rss_feeds", status="failed", error="parse error")

        report = build_extraction_diagnostics_report(limit_cycles=5, path=db_path)
        connectors = {c["connector"]: c for c in report["by_connector"]}
        assert connectors["reliefweb"]["ok_rate"] == 1.0
        assert connectors["rss_feeds"]["ok_rate"] == pytest.approx(0.2, abs=0.01)

    def test_by_connector_sorted_by_ok_rate_ascending(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        # high-failure connector first in data, should appear first after sort
        for _ in range(4):
            _seed_extraction(db_path, cid, connector="bad_conn", status="failed", error="err")
        _seed_extraction(db_path, cid, connector="bad_conn", status="ok")
        for _ in range(5):
            _seed_extraction(db_path, cid, connector="good_conn", status="ok")

        report = build_extraction_diagnostics_report(limit_cycles=5, path=db_path)
        rates = [c["ok_rate"] for c in report["by_connector"]]
        assert rates == sorted(rates), "by_connector should be sorted by ok_rate asc"

    def test_avg_char_count_in_by_connector(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        _seed_extraction(db_path, cid, connector="reliefweb", status="ok", char_count=1000)
        _seed_extraction(db_path, cid, connector="reliefweb", status="ok", char_count=2000)

        report = build_extraction_diagnostics_report(limit_cycles=5, path=db_path)
        rw = next(c for c in report["by_connector"] if c["connector"] == "reliefweb")
        assert rw["avg_char_count"] == 1500

    def test_by_method_total_and_ok_rate(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        for _ in range(3):
            _seed_extraction(db_path, cid, method="pdfplumber", status="ok")
        for _ in range(1):
            _seed_extraction(db_path, cid, method="pdfplumber", status="failed", error="e")
        for _ in range(2):
            _seed_extraction(db_path, cid, method="trafilatura", status="ok")

        report = build_extraction_diagnostics_report(limit_cycles=5, path=db_path)
        methods = {m["method"]: m for m in report["by_method"]}
        assert methods["pdfplumber"]["total"] == 4
        assert methods["pdfplumber"]["ok"] == 3
        assert methods["pdfplumber"]["ok_rate"] == pytest.approx(0.75, abs=0.01)
        assert methods["trafilatura"]["total"] == 2
        assert methods["trafilatura"]["ok_rate"] == 1.0

    def test_top_errors_limited_to_10(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        # Seed 11 distinct error messages
        for i in range(11):
            _seed_extraction(
                db_path, cid,
                status="failed",
                error=f"unique_error_{i:02d}",
                method="pdfplumber",
                attachment_url=f"https://example.org/doc{i}.pdf",
            )

        report = build_extraction_diagnostics_report(limit_cycles=5, path=db_path)
        assert len(report["top_errors"]) <= 10

    def test_top_errors_sorted_by_count_descending(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        # "common error" appears 5 times, "rare error" appears 1 time
        for i in range(5):
            _seed_extraction(
                db_path, cid, status="failed", error="common error", method="pdfplumber",
                attachment_url=f"https://example.org/a{i}.pdf",
            )
        _seed_extraction(
            db_path, cid, status="failed", error="rare error", method="pdfplumber",
            attachment_url="https://example.org/b0.pdf",
        )

        report = build_extraction_diagnostics_report(limit_cycles=5, path=db_path)
        assert report["top_errors"][0]["error"] == "common error"
        assert report["top_errors"][0]["count"] == 5

    def test_low_yield_requires_minimum_3_records(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        # 2 failed records for "tiny_conn" — below min threshold → NOT flagged
        for _ in range(2):
            _seed_extraction(db_path, cid, connector="tiny_conn", status="failed", error="e")
        # 3 failed records for "big_bad_conn" — at/above threshold → flagged
        for _ in range(3):
            _seed_extraction(db_path, cid, connector="big_bad_conn", status="failed", error="e")

        report = build_extraction_diagnostics_report(limit_cycles=5, path=db_path)
        assert "tiny_conn" not in report["low_yield_connectors"]
        assert "big_bad_conn" in report["low_yield_connectors"]

    def test_connector_filter_excludes_others(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        cid = _seed_cycle(db_path)
        _seed_extraction(db_path, cid, connector="reliefweb", status="ok")
        _seed_extraction(db_path, cid, connector="rss_feeds", status="ok")

        report = build_extraction_diagnostics_report(limit_cycles=5, connector="reliefweb", path=db_path)
        assert report["total_records"] == 1
        connectors = [c["connector"] for c in report["by_connector"]]
        assert "reliefweb" in connectors
        assert "rss_feeds" not in connectors

    def test_limit_cycles_excludes_older_records(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        old_cid = _seed_cycle(db_path)
        new_cid = _seed_cycle(db_path)
        # record in old cycle only
        _seed_extraction(db_path, old_cid, connector="reliefweb", status="ok", char_count=500)
        # record in new cycle
        _seed_extraction(db_path, new_cid, connector="reliefweb", status="ok", char_count=800)

        # limit_cycles=1 → only the newest cycle should be analysed
        report = build_extraction_diagnostics_report(limit_cycles=1, path=db_path)
        assert report["total_records"] == 1
        rw = next(c for c in report["by_connector"] if c["connector"] == "reliefweb")
        assert rw["avg_char_count"] == 800

    def test_cycles_analyzed_in_report(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monitoring.db"
        init_db(db_path)
        _seed_cycle(db_path)
        _seed_cycle(db_path)
        _seed_cycle(db_path)

        report = build_extraction_diagnostics_report(limit_cycles=2, path=db_path)
        assert report["cycles_analyzed"] == 2


# ────────────────────────────────────────────────────────────────────
# TestExtractionReportCLI
# ────────────────────────────────────────────────────────────────────

class TestExtractionReportCLI:
    """CLI smoke tests for the extraction-report subcommand (Phase 9.4)."""

    def test_cli_outputs_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """extraction-report with no data returns parseable JSON."""
        fake_report = {
            "total_records": 0, "cycles_analyzed": 0,
            "by_status": {}, "by_connector": [], "by_method": [],
            "top_errors": [], "low_yield_connectors": [],
        }
        with patch(
            "agent_hum_crawler.main.build_extraction_diagnostics_report",
            return_value=fake_report,
        ):
            from agent_hum_crawler.main import main
            rc = main(["extraction-report"])
        assert rc == 0
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["total_records"] == 0

    def test_cli_passes_limit_cycles(self) -> None:
        """--limit-cycles argument is forwarded to build_extraction_diagnostics_report."""
        with patch(
            "agent_hum_crawler.main.build_extraction_diagnostics_report",
            return_value={"total_records": 0, "cycles_analyzed": 5,
                          "by_status": {}, "by_connector": [], "by_method": [],
                          "top_errors": [], "low_yield_connectors": []},
        ) as mock_fn:
            from agent_hum_crawler.main import main
            main(["extraction-report", "--limit-cycles", "5"])
        mock_fn.assert_called_once_with(limit_cycles=5, connector=None)

    def test_cli_passes_connector_filter(self) -> None:
        """--connector argument is forwarded correctly."""
        with patch(
            "agent_hum_crawler.main.build_extraction_diagnostics_report",
            return_value={"total_records": 1, "cycles_analyzed": 20,
                          "by_status": {"ok": 1}, "by_connector": [], "by_method": [],
                          "top_errors": [], "low_yield_connectors": []},
        ) as mock_fn:
            from agent_hum_crawler.main import main
            main(["extraction-report", "--connector", "reliefweb"])
        mock_fn.assert_called_once_with(limit_cycles=20, connector="reliefweb")

    def test_cli_empty_connector_treated_as_none(self) -> None:
        """Omitting --connector results in connector=None (no filter)."""
        with patch(
            "agent_hum_crawler.main.build_extraction_diagnostics_report",
            return_value={"total_records": 0, "cycles_analyzed": 0,
                          "by_status": {}, "by_connector": [], "by_method": [],
                          "top_errors": [], "low_yield_connectors": []},
        ) as mock_fn:
            from agent_hum_crawler.main import main
            main(["extraction-report"])
        _, kwargs = mock_fn.call_args
        assert kwargs["connector"] is None

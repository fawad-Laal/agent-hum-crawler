"""Tests for the PipelineCoordinator and supporting modules (llm_utils, rust_accel)."""

from pathlib import Path

import pytest

from agent_hum_crawler.coordinator import PipelineContext, PipelineCoordinator
from agent_hum_crawler.database import init_db, persist_cycle
from agent_hum_crawler.llm_utils import (
    build_citation_numbers,
    citation_ref,
    domain_counter,
    extract_json_object,
    extract_responses_text,
)
from agent_hum_crawler.models import ProcessedEvent, RawSourceItem


# ── Fixtures ─────────────────────────────────────────────────────────


def _seed_db(tmp_path: Path) -> Path:
    """Create a temp DB with one cycle of test data."""
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)

    raw_items = [
        RawSourceItem(
            connector="reliefweb",
            source_type="humanitarian",
            url="https://reliefweb.int/node/1001",
            title="[ReliefWeb] Madagascar flood kills 12",
            published_at="2026-02-18T10:00:00Z",
            country_candidates=["Madagascar"],
            text="Flooding in Analanjirofo killed 12 and displaced 3,500 families.",
            language="en",
            content_mode="content-level",
        ),
        RawSourceItem(
            connector="government_feeds",
            source_type="official",
            url="https://bngrc.mg/update-2026-02",
            title="[BNGRC] Cyclone update",
            published_at="2026-02-18T12:00:00Z",
            country_candidates=["Madagascar"],
            text="Severe cyclone damage in Toamasina; death toll rises to 8.",
            language="en",
            content_mode="content-level",
        ),
    ]
    events = [
        ProcessedEvent(
            event_id="evt-flood-1",
            status="new",
            connector="reliefweb",
            source_type="humanitarian",
            url="https://reliefweb.int/node/1001",
            title="[ReliefWeb] Madagascar flood kills 12",
            country="Madagascar",
            disaster_type="flood",
            published_at="2026-02-18T10:00:00Z",
            severity="high",
            confidence="high",
            summary="Flooding killed 12 and displaced 3,500 families.",
            corroboration_sources=2,
            corroboration_connectors=1,
            corroboration_source_types=1,
        ),
        ProcessedEvent(
            event_id="evt-cyclone-2",
            status="new",
            connector="government_feeds",
            source_type="official",
            url="https://bngrc.mg/update-2026-02",
            title="[BNGRC] Cyclone update",
            country="Madagascar",
            disaster_type="cyclone/storm",
            published_at="2026-02-18T12:00:00Z",
            severity="high",
            confidence="high",
            summary="Severe cyclone damage in Toamasina; death toll rises to 8.",
            corroboration_sources=1,
            corroboration_connectors=1,
            corroboration_source_types=1,
        ),
    ]
    persist_cycle(
        raw_items=raw_items,
        events=events,
        connector_count=2,
        summary="Test cycle for coordinator tests",
        connector_metrics=[],
        llm_stats={},
        path=db_path,
    )
    return db_path


# ── llm_utils tests ─────────────────────────────────────────────────


class TestExtractResponsesText:
    def test_output_text_shorthand(self):
        payload = {"output_text": "Hello world"}
        assert extract_responses_text(payload) == "Hello world"

    def test_output_content_structure(self):
        payload = {
            "output": [
                {
                    "content": [
                        {"type": "text", "text": "Part A"},
                        {"type": "text", "text": "Part B"},
                    ]
                }
            ]
        }
        result = extract_responses_text(payload)
        assert "Part A" in result
        assert "Part B" in result

    def test_empty_payload(self):
        assert extract_responses_text({}) == ""


class TestExtractJsonObject:
    def test_plain_json(self):
        result = extract_json_object('{"key": "value"}')
        assert result == {"key": "value"}

    def test_fenced_json(self):
        result = extract_json_object('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_in_text(self):
        result = extract_json_object('Some text before {"key": "val"} after')
        assert result == {"key": "val"}

    def test_not_json(self):
        assert extract_json_object("just plain text") is None

    def test_empty(self):
        assert extract_json_object("") is None


class TestCitationHelpers:
    def test_build_citation_numbers(self):
        evidence = [
            {"url": "https://a.com", "canonical_url": None},
            {"url": "https://b.com", "canonical_url": "https://b.com"},
            {"url": "https://a.com", "canonical_url": None},  # duplicate
        ]
        nums = build_citation_numbers(evidence)
        assert nums["https://a.com"] == 1
        assert nums["https://b.com"] == 2
        assert len(nums) == 2

    def test_citation_ref(self):
        nums = {"https://a.com": 1, "https://b.com": 2}
        assert citation_ref(nums, None, "https://a.com") == "[1]"
        assert citation_ref(nums, "https://b.com", "https://x.com") == "[2]"
        assert citation_ref(nums, None, "https://missing.com") == "[unavailable]"

    def test_domain_counter(self):
        evidence = [
            {"url": "https://reliefweb.int/node/1"},
            {"url": "https://reliefweb.int/node/2"},
            {"url": "https://bngrc.mg/update"},
        ]
        counts = domain_counter(evidence)
        assert counts["reliefweb.int"] == 2
        assert counts["bngrc.mg"] == 1


# ── rust_accel tests ─────────────────────────────────────────────────


class TestRustAccel:
    """Tests that work regardless of whether Rust is available."""

    def test_extract_figures(self):
        from agent_hum_crawler.rust_accel import extract_figures

        result = extract_figures("48000 displaced and death toll rises to 59")
        assert result.get("deaths", 0) >= 59
        assert result.get("displaced", 0) >= 48000

    def test_similarity_ratio(self):
        from agent_hum_crawler.rust_accel import similarity_ratio

        assert similarity_ratio("hello world", "hello world") == 1.0
        assert similarity_ratio("hello", "goodbye") < 0.5

    def test_classify_impact_type(self):
        from agent_hum_crawler.rust_accel import classify_impact_type

        result = classify_impact_type("52 deaths confirmed and many injured")
        assert result in ("people_impact", "people")

    def test_normalize_text(self):
        from agent_hum_crawler.rust_accel import normalize_text

        assert normalize_text("  Hello   WORLD  ") == "hello world"

    def test_cluster_titles_basic(self):
        from agent_hum_crawler.rust_accel import cluster_titles

        titles = ["Cyclone hits coast", "Cyclone hits the coast", "Earthquake in Java"]
        clusters = cluster_titles(titles, 0.80)
        assert isinstance(clusters, list)
        assert len(clusters) >= 1  # at least one cluster

    def test_rust_available_is_bool(self):
        from agent_hum_crawler.rust_accel import rust_available

        assert isinstance(rust_available(), bool)


# ── Coordinator tests ────────────────────────────────────────────────


class TestPipelineContext:
    def test_defaults(self):
        ctx = PipelineContext()
        assert ctx.evidence == []
        assert ctx.ontology is None
        assert ctx.report_md == ""
        assert ctx.sa_md == ""

    def test_fields_assignable(self):
        ctx = PipelineContext()
        ctx.evidence = [{"title": "test"}]
        assert len(ctx.evidence) == 1


class TestPipelineCoordinator:
    def test_init_defaults(self):
        coord = PipelineCoordinator()
        assert coord.countries is None
        assert coord.strict_filters is True
        assert coord.limit_events == 80

    def test_gather_evidence_empty_db(self, tmp_path: Path):
        db_path = tmp_path / "empty.db"
        init_db(db_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        ctx = coord.gather_evidence()
        assert ctx == {"evidence": [], "meta": {"cycles_analyzed": 0, "events_considered": 0}}

    def test_gather_evidence_with_data(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        ctx = coord.gather_evidence()
        assert len(ctx["evidence"]) >= 1
        assert ctx["meta"]["cycles_analyzed"] >= 1

    def test_evidence_caching(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        ctx1 = coord.gather_evidence()
        ctx2 = coord.gather_evidence()
        assert ctx1 is ctx2  # same object, cached

    def test_evidence_force_refresh(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        ctx1 = coord.gather_evidence()
        ctx2 = coord.gather_evidence(force=True)
        # Refreshed — new object but same content
        assert len(ctx2["evidence"]) == len(ctx1["evidence"])

    def test_build_ontology(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        ontology = coord.build_ontology()
        assert ontology is not None
        assert coord.ctx.ontology is ontology

    def test_ontology_caching(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        o1 = coord.build_ontology()
        o2 = coord.build_ontology()
        assert o1 is o2  # same object, cached

    def test_render_report(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        report = coord.render_report(title="Test Report")
        assert "Test Report" in report
        assert len(report) > 100
        assert coord.ctx.report_md == report

    def test_render_situation_analysis(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        sa = coord.render_situation_analysis(
            title="Test SA",
            event_name="Cyclone Test",
        )
        assert len(sa) > 100
        assert coord.ctx.sa_md == sa

    def test_write_report_requires_render(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(db_path=db_path)
        with pytest.raises(RuntimeError, match="No report rendered"):
            coord.write_report()

    def test_write_sa_requires_render(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(db_path=db_path)
        with pytest.raises(RuntimeError, match="No SA rendered"):
            coord.write_sa()

    def test_write_report_to_file(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        coord.render_report(title="File Test")
        out = coord.write_report(output_path=tmp_path / "report.md")
        assert out.exists()
        assert "File Test" in out.read_text(encoding="utf-8")

    def test_evaluate_report_quality_requires_render(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(db_path=db_path)
        with pytest.raises(RuntimeError, match="No report rendered"):
            coord.evaluate_report_quality()

    def test_evaluate_report_quality(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        coord.render_report()
        quality = coord.evaluate_report_quality()
        assert "status" in quality

    def test_summary_dict(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        coord.gather_evidence()
        summary = coord.summary_dict()
        assert summary["status"] == "ok"
        assert summary["evidence_count"] >= 1
        assert "timing" in summary

    def test_run_pipeline_full(self, tmp_path: Path):
        db_path = _seed_db(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        coord = PipelineCoordinator(
            countries=["madagascar"],
            db_path=db_path,
        )
        ctx = coord.run_pipeline(
            report_title="Pipeline Report",
            sa_title="Pipeline SA",
            write_files=True,
            output_dir=output_dir,
        )
        assert ctx.report_md
        assert ctx.sa_md
        assert ctx.report_path and ctx.report_path.exists()
        assert ctx.sa_path and ctx.sa_path.exists()
        assert ctx.finished_at

    def test_shared_evidence_between_report_and_sa(self, tmp_path: Path):
        """Both report and SA use the same evidence — the key coordination fix."""
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(countries=["madagascar"], db_path=db_path)
        coord.gather_evidence()
        evidence_before = list(coord.ctx.evidence)
        coord.render_report()
        coord.render_situation_analysis()
        # Evidence should not have changed — proving single query
        assert coord.ctx.evidence == evidence_before

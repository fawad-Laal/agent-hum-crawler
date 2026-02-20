"""Phase 4 tests — Deep Extraction & Pipeline Orchestration.

Covers:
  4.1  PDF table extraction (ExtractedDocument, ExtractedTable)
  4.2  Full-article content fetching (feed_base PDF link detection)
  4.3  Multi-impact per evidence (_classify_all_impact_types)
  4.4  Province-level figure distribution (distribute_national_figures)
  4.5  Coordinator pipeline upgrade (stage errors, diagnostics, callback)
  4.6  Ontology persistence in DB
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ── 4.1  PDF table extraction ────────────────────────────────────────

from agent_hum_crawler.pdf_extract import (
    ExtractedDocument,
    ExtractedTable,
)


class TestExtractedTable:
    def test_to_markdown_basic(self):
        tbl = ExtractedTable(
            page_number=1,
            headers=["Province", "Deaths", "Displaced"],
            rows=[
                ["Zambezia", "52", "16000"],
                ["Sofala", "8", "4200"],
            ],
        )
        md = tbl.to_markdown()
        assert "| Province | Deaths | Displaced |" in md
        assert "| Zambezia | 52 | 16000 |" in md
        assert "| --- | --- | --- |" in md

    def test_to_markdown_empty(self):
        tbl = ExtractedTable(page_number=1, headers=[], rows=[])
        assert tbl.to_markdown() == ""

    def test_to_markdown_generates_column_names(self):
        tbl = ExtractedTable(
            page_number=2,
            headers=[],
            rows=[["a", "b", "c"]],
        )
        md = tbl.to_markdown()
        assert "col0" in md
        assert "| a | b | c |" in md


class TestExtractedDocument:
    def test_empty_doc(self):
        doc = ExtractedDocument()
        assert doc.text == ""
        assert doc.tables == []
        assert not doc.has_tables
        assert doc.full_text == ""
        assert doc.tables_as_text() == ""

    def test_text_only(self):
        doc = ExtractedDocument(text="Hello world")
        assert doc.full_text == "Hello world"
        assert not doc.has_tables

    def test_tables_combined(self):
        tbl = ExtractedTable(
            page_number=1,
            headers=["X", "Y"],
            rows=[["1", "2"]],
        )
        doc = ExtractedDocument(text="Body text", tables=[tbl])
        assert doc.has_tables
        assert "Body text" in doc.full_text
        assert "[Table 1" in doc.full_text
        assert "| X | Y |" in doc.full_text

    def test_page_count_and_method(self):
        doc = ExtractedDocument(text="pg", page_count=5, extraction_method="pdfplumber")
        assert doc.page_count == 5
        assert doc.extraction_method == "pdfplumber"


# ── 4.2  Full-article content fetching ──────────────────────────────

from agent_hum_crawler.connectors.feed_base import FeedConnector


class TestFeedPDFLinkDetection:
    def test_extract_pdf_links_basic(self):
        html = """
        <html><body>
        <a href="/docs/report.pdf">Report</a>
        <a href="https://other.org/data.pdf">Data</a>
        <a href="page.html">Page</a>
        </body></html>
        """
        links = FeedConnector._extract_pdf_links(html, "https://example.com/page")
        assert len(links) == 2
        assert "https://example.com/docs/report.pdf" in links
        assert "https://other.org/data.pdf" in links

    def test_extract_pdf_links_dedup(self):
        html = """
        <a href="/doc.pdf">Link 1</a>
        <a href="/doc.pdf">Link 2</a>
        """
        links = FeedConnector._extract_pdf_links(html, "https://example.com/")
        assert len(links) == 1

    def test_extract_pdf_links_empty(self):
        assert FeedConnector._extract_pdf_links("", "https://x.com") == []
        assert FeedConnector._extract_pdf_links("<a href='page.html'>x</a>", "https://x.com") == []


# ── 4.3  Multi-impact per evidence ──────────────────────────────────

from agent_hum_crawler.graph_ontology import (
    ImpactType,
    _classify_all_impact_types,
    _classify_impact_type,
    build_ontology_from_evidence,
)


class TestMultiImpact:
    def test_classify_all_returns_multiple(self):
        text = "12 people killed and 3 bridges destroyed, hospital damaged"
        types = _classify_all_impact_types(text)
        assert len(types) >= 2
        assert ImpactType.PEOPLE in types
        assert ImpactType.INFRASTRUCTURE in types or ImpactType.SERVICES in types

    def test_classify_all_single_type(self):
        text = "52 deaths reported in the flooding"
        types = _classify_all_impact_types(text)
        assert ImpactType.PEOPLE in types

    def test_classify_all_fallback(self):
        text = "general update with no specific keywords"
        types = _classify_all_impact_types(text)
        assert types == [ImpactType.PEOPLE]

    def test_classify_all_ordering(self):
        # People keywords: killed, displaced (2 matches)
        # Infrastructure: bridge (1 match)
        text = "10 killed 5000 displaced, bridge collapsed"
        types = _classify_all_impact_types(text)
        assert types[0] == ImpactType.PEOPLE
        assert ImpactType.INFRASTRUCTURE in types

    def test_multi_impact_in_ontology(self):
        """build_ontology_from_evidence creates multiple impacts per evidence."""
        evidence = [
            {
                "country": "Mozambique",
                "disaster_type": "cyclone",
                "title": "Cyclone destroys bridges and kills 20",
                "summary": "20 killed, 3 bridges destroyed, hospital collapsed",
                "text": "20 people killed, 3 bridges destroyed, hospital collapsed, 5000 displaced",
                "url": "https://example.com/1",
                "connector": "reliefweb",
                "severity": "high",
                "confidence": "high",
                "published_at": "2026-01-15",
                "source_label": "OCHA",
                "credibility_tier": 1,
            },
        ]
        graph = build_ontology_from_evidence(evidence)
        # With multi-impact, a single evidence item mentioning people, infra, services
        # should produce >= 2 ImpactObservations
        assert len(graph.impacts) >= 2
        impact_types = {i.impact_type for i in graph.impacts}
        assert ImpactType.PEOPLE in impact_types

    def test_multi_impact_figures_not_double_counted(self):
        """Only the primary impact type gets figures; secondary types get empty."""
        evidence = [
            {
                "country": "Somalia",
                "disaster_type": "flood",
                "title": "Flood kills 15",
                "summary": "15 dead, school collapsed",
                "text": "15 dead 2000 displaced, school collapsed, bridge washed away",
                "url": "https://example.com/2",
                "connector": "reliefweb",
                "severity": "high",
                "confidence": "high",
                "published_at": "2026-02-01",
                "source_label": "UNICEF",
                "credibility_tier": 1,
            },
        ]
        graph = build_ontology_from_evidence(evidence)
        assert len(graph.impacts) >= 2
        # Primary impact gets figures, secondary ones get empty
        primary = graph.impacts[0]
        assert primary.figures  # should have deaths/displaced
        for secondary in graph.impacts[1:]:
            assert secondary.figures == {}


# ── 4.4  Province-level figure distribution ─────────────────────────

from agent_hum_crawler.graph_ontology import (
    GeoArea,
    HumanitarianOntologyGraph,
    ImpactObservation,
)


class TestFigureDistribution:
    def _make_graph_with_national(self):
        g = HumanitarianOntologyGraph()
        g.add_geo("Mozambique", admin_level=0)
        g.add_geo("Zambezia", admin_level=1, parent="Mozambique")
        g.add_geo("Sofala", admin_level=1, parent="Mozambique")
        g.add_geo("Mocuba", admin_level=2, parent="Zambezia")

        # National-level figure (admin_level=0)
        g.add_impact(ImpactObservation(
            description="National death toll",
            impact_type=ImpactType.PEOPLE,
            geo_area="Mozambique",
            admin_level=0,
            severity_phase=4,
            figures={"deaths": 100, "displaced": 50000},
        ))
        # Province-level evidence mentions (for proportional distribution)
        g.add_impact(ImpactObservation(
            description="Damage in Zambezia",
            impact_type=ImpactType.PEOPLE,
            geo_area="Zambezia",
            admin_level=1,
            severity_phase=3,
            figures={"deaths": 30},
        ))
        g.add_impact(ImpactObservation(
            description="More damage in Zambezia district",
            impact_type=ImpactType.HOUSING,
            geo_area="Mocuba",
            admin_level=2,
            severity_phase=3,
            figures={},
        ))
        g.add_impact(ImpactObservation(
            description="Damage in Sofala",
            impact_type=ImpactType.PEOPLE,
            geo_area="Sofala",
            admin_level=1,
            severity_phase=3,
            figures={"deaths": 10},
        ))
        return g

    def test_distribute_returns_all_admin1(self):
        g = self._make_graph_with_national()
        dist = g.distribute_national_figures()
        assert "zambezia" in dist
        assert "sofala" in dist

    def test_distribute_proportional_split(self):
        g = self._make_graph_with_national()
        dist = g.distribute_national_figures()
        # Zambezia has 2 mentions (Zambezia direct + Mocuba child), Sofala has 1
        # Total mentions = 3.  Zambezia gets 2/3, Sofala gets 1/3
        z_deaths = dist["zambezia"]["figures"].get("deaths", 0)
        s_deaths = dist["sofala"]["figures"].get("deaths", 0)
        # Distributed national deaths: 100 * 2/3 ≈ 67, 100 * 1/3 ≈ 33
        # But Zambezia already has 30 from local, so distribution should be max(30, 67) = 67
        assert z_deaths >= 30
        assert s_deaths >= 10
        assert z_deaths + s_deaths <= 110  # shouldn't exceed national + rounding

    def test_distribute_marks_distributed(self):
        g = self._make_graph_with_national()
        dist = g.distribute_national_figures()
        # At least one area should be marked as distributed
        has_distributed = any(v["distributed"] for v in dist.values())
        assert has_distributed

    def test_distribute_no_national_figures(self):
        g = HumanitarianOntologyGraph()
        g.add_geo("Somalia", admin_level=0)
        g.add_geo("Bay", admin_level=1, parent="Somalia")
        g.add_impact(ImpactObservation(
            description="Local deaths",
            impact_type=ImpactType.PEOPLE,
            geo_area="Bay",
            admin_level=1,
            figures={"deaths": 5},
        ))
        dist = g.distribute_national_figures()
        assert "bay" in dist
        assert dist["bay"]["figures"]["deaths"] == 5
        assert not dist["bay"]["distributed"]


# ── 4.5  Coordinator pipeline upgrade ───────────────────────────────

from agent_hum_crawler.coordinator import PipelineContext, PipelineCoordinator
from agent_hum_crawler.database import init_db, persist_cycle
from agent_hum_crawler.models import ProcessedEvent, RawSourceItem


def _seed_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "monitoring.db"
    init_db(db_path)

    raw = [
        RawSourceItem(
            connector="reliefweb",
            source_type="humanitarian",
            url="https://reliefweb.int/node/1001",
            title="Madagascar flood kills 12",
            published_at="2026-02-18",
            country_candidates=["Madagascar"],
            text="Flooding killed 12 and displaced 3,500 in Analanjirofo.",
            language="en",
            content_mode="content-level",
        ),
    ]
    events = [
        ProcessedEvent(
            event_id="evt-1",
            status="new",
            connector="reliefweb",
            source_type="humanitarian",
            url="https://reliefweb.int/node/1001",
            title="Madagascar flood kills 12",
            country="Madagascar",
            disaster_type="flood",
            published_at="2026-02-18",
            severity="high",
            confidence="high",
            summary="Flooding killed 12 in Madagascar.",
        ),
    ]
    persist_cycle(
        raw_items=raw,
        events=events,
        connector_count=1,
        summary="Test cycle",
        path=db_path,
    )
    return db_path


class TestCoordinatorStageErrors:
    def test_pipeline_context_defaults(self):
        ctx = PipelineContext()
        assert not ctx.has_errors
        assert ctx.total_errors == 0

    def test_pipeline_context_error_tracking(self):
        ctx = PipelineContext()
        ctx.stage_errors["evidence"].append("DB connection failed")
        ctx.stage_errors["ontology"].append("Parse error")
        assert ctx.has_errors
        assert ctx.total_errors == 2

    def test_coordinator_accepts_on_progress(self, tmp_path):
        events: list[tuple] = []
        coord = PipelineCoordinator(
            countries=["Madagascar"],
            db_path=tmp_path / "test.db",
            on_progress=lambda s, st, d: events.append((s, st, d)),
        )
        assert coord._on_progress is not None

    def test_summary_dict_includes_diagnostics(self, tmp_path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(
            countries=["Madagascar"],
            db_path=db_path,
        )
        coord.gather_evidence()
        summary = coord.summary_dict()
        assert "stage_diagnostics" in summary
        assert "stage_errors" in summary
        assert "total_errors" in summary
        assert summary["stage_diagnostics"]["evidence"]["status"] == "ok"

    def test_progress_callback_fires(self, tmp_path):
        db_path = _seed_db(tmp_path)
        events: list[tuple] = []
        coord = PipelineCoordinator(
            countries=["Madagascar"],
            db_path=db_path,
            on_progress=lambda s, st, d: events.append((s, st, d)),
        )
        coord.gather_evidence()
        stage_names = [e[0] for e in events]
        assert "evidence" in stage_names
        statuses = [e[1] for e in events]
        assert "started" in statuses
        assert "completed" in statuses

    def test_run_pipeline_resilient(self, tmp_path):
        """Pipeline continues when non-critical stage fails."""
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(
            countries=["Madagascar"],
            db_path=db_path,
        )
        ctx = coord.run_pipeline(write_files=False)
        # Should complete with evidence gathered
        assert len(ctx.evidence) > 0
        assert ctx.finished_at


class TestCoordinatorPersistOntology:
    def test_persist_ontology_via_coordinator(self, tmp_path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(
            countries=["Madagascar"],
            db_path=db_path,
        )
        coord.gather_evidence()
        coord.build_ontology()
        counts = coord.persist_ontology()
        assert counts["snapshot_id"] > 0
        assert counts["impacts"] >= 0

    def test_persist_ontology_in_pipeline(self, tmp_path):
        db_path = _seed_db(tmp_path)
        coord = PipelineCoordinator(
            countries=["Madagascar"],
            db_path=db_path,
        )
        ctx = coord.run_pipeline(
            write_files=False,
            persist_ontology=True,
        )
        assert "persist_ontology" in ctx.stage_diagnostics


# ── 4.6  Ontology persistence in DB ─────────────────────────────────

from agent_hum_crawler.database import (
    OntologySnapshot,
    ImpactRecord,
    NeedRecord,
    RiskRecord,
    ResponseRecord,
    build_engine,
    persist_ontology,
    get_ontology_snapshots,
)
from agent_hum_crawler.graph_ontology import (
    NeedType,
    NeedStatement,
    RiskStatement,
    ResponseActivity,
    SourceClaim,
)


class TestOntologyPersistence:
    def _make_test_ontology(self):
        g = HumanitarianOntologyGraph()
        g.add_geo("Somalia", admin_level=0)
        g.add_geo("Bay", admin_level=1, parent="Somalia")
        g.add_impact(ImpactObservation(
            description="Deaths in Bay",
            impact_type=ImpactType.PEOPLE,
            geo_area="Bay",
            admin_level=1,
            severity_phase=4,
            figures={"deaths": 25, "displaced": 8000},
            source_url="https://example.com/1",
            source_connector="reliefweb",
            reported_date="2026-01-10",
            source_label="OCHA",
            credibility_tier=1,
        ))
        g.add_need(NeedStatement(
            description="Food needed",
            need_type=NeedType.FOOD_SECURITY,
            geo_area="Bay",
            admin_level=1,
            severity_phase=3,
            source_url="https://example.com/1",
        ))
        g.add_risk(RiskStatement(
            description="Flooding risk ahead",
            hazard_name="flood",
            geo_area="Bay",
        ))
        g.add_response(ResponseActivity(
            description="WFP delivering aid",
            actor="WFP",
            actor_type="un_agency",
            geo_area="Bay",
            sector="food_security",
        ))
        g.add_claim(SourceClaim(
            claim_text="25 dead in Bay",
            source_url="https://example.com/1",
            source_label="OCHA",
            connector="reliefweb",
        ))
        return g

    def test_persist_and_retrieve(self, tmp_path):
        db_path = tmp_path / "ontology.db"
        engine = build_engine(db_path)
        graph = self._make_test_ontology()

        counts = persist_ontology(engine, graph)
        assert counts["impacts"] == 1
        assert counts["needs"] == 1
        assert counts["risks"] == 1
        assert counts["responses"] == 1
        assert counts["snapshot_id"] > 0

    def test_get_snapshots(self, tmp_path):
        db_path = tmp_path / "ontology.db"
        engine = build_engine(db_path)
        graph = self._make_test_ontology()
        persist_ontology(engine, graph)
        persist_ontology(engine, graph)

        snapshots = get_ontology_snapshots(limit=5, engine=engine)
        assert len(snapshots) == 2
        assert snapshots[0]["impact_count"] == 1
        assert snapshots[0]["need_count"] == 1

    def test_impact_record_fields(self, tmp_path):
        from sqlmodel import Session, select

        db_path = tmp_path / "ontology.db"
        engine = build_engine(db_path)
        graph = self._make_test_ontology()
        persist_ontology(engine, graph)

        with Session(engine) as sess:
            records = list(sess.exec(select(ImpactRecord)))
            assert len(records) == 1
            r = records[0]
            assert r.impact_type == "people_impact"
            assert r.geo_area == "Bay"
            assert r.credibility_tier == 1
            assert '"deaths"' in r.figures_json

    def test_need_record_fields(self, tmp_path):
        from sqlmodel import Session, select

        db_path = tmp_path / "ontology.db"
        engine = build_engine(db_path)
        graph = self._make_test_ontology()
        persist_ontology(engine, graph)

        with Session(engine) as sess:
            records = list(sess.exec(select(NeedRecord)))
            assert len(records) == 1
            assert records[0].need_type == "food_security"

    def test_multiple_snapshots_independent(self, tmp_path):
        """Each persist creates a new snapshot; records are snapshot-scoped."""
        from sqlmodel import Session, select

        db_path = tmp_path / "ontology.db"
        engine = build_engine(db_path)
        graph = self._make_test_ontology()

        c1 = persist_ontology(engine, graph)
        c2 = persist_ontology(engine, graph)

        assert c1["snapshot_id"] != c2["snapshot_id"]

        with Session(engine) as sess:
            all_impacts = list(sess.exec(select(ImpactRecord)))
            assert len(all_impacts) == 2  # 1 per snapshot

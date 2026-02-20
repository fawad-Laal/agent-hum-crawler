"""Tests for situation_analysis module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_hum_crawler.situation_analysis import (
    load_sa_template,
    render_situation_analysis,
    write_situation_analysis,
    _render_event_card,
    _render_key_figures,
    _render_national_impact_table,
    _render_admin1_table,
    _build_admin2_row,
)
from agent_hum_crawler.graph_ontology import (
    HumanitarianOntologyGraph,
    HazardCategory,
    ImpactObservation,
    ImpactType,
    NeedStatement,
    NeedType,
    RiskStatement,
)


# ── Fixtures ─────────────────────────────────────────────────────────


def _sample_evidence() -> list[dict]:
    return [
        {
            "event_id": "evt-001",
            "title": "Cyclone hits Zambezia",
            "country": "Mozambique",
            "disaster_type": "cyclone/storm",
            "connector": "reliefweb",
            "source_type": "api",
            "severity": "high",
            "confidence": "high",
            "summary": "52 deaths and 16000 displaced people in Zambezia",
            "url": "https://reliefweb.int/report/1",
            "canonical_url": "https://reliefweb.int/report/1",
            "published_at": "2026-03-04T10:00:00Z",
            "text": "Tropical Cyclone Gezani-26 caused 52 deaths in Zambezia province.",
            "corroboration_sources": 3,
            "graph_score": 15.0,
            "source_label": "ReliefWeb",
        },
        {
            "event_id": "evt-002",
            "title": "Flood damage in Sofala",
            "country": "Mozambique",
            "disaster_type": "flood",
            "connector": "government_feeds",
            "source_type": "rss",
            "severity": "medium",
            "confidence": "medium",
            "summary": "4200 houses damaged by flooding in Beira district",
            "url": "https://ingd.gov.mz/report/2",
            "canonical_url": None,
            "published_at": "2026-03-05T08:00:00Z",
            "text": "Flooding in Beira has damaged 4200 houses and displaced 8000 people.",
            "corroboration_sources": 2,
            "graph_score": 10.0,
            "source_label": "INGD",
        },
    ]


def _sample_graph_context() -> dict:
    return {
        "evidence": _sample_evidence(),
        "meta": {
            "cycles_analyzed": 5,
            "events_considered": 20,
            "events_selected": 2,
            "by_country": {"Mozambique": 2},
            "by_disaster_type": {"cyclone/storm": 1, "flood": 1},
            "by_connector": {"reliefweb": 1, "government_feeds": 1},
            "by_source_type": {"api": 1, "rss": 1},
        },
    }


def _sample_hierarchy() -> dict[str, list[str]]:
    return {
        "Zambezia": ["Mocuba", "Quelimane", "Namacurra"],
        "Sofala": ["Beira", "Dondo"],
    }


# ── Template loading ─────────────────────────────────────────────────


class TestLoadTemplate:
    def test_loads_default_template(self):
        # Uses config/report_template.situation_analysis.json if present
        tpl = load_sa_template()
        assert "sections" in tpl
        assert "executive_summary" in tpl["sections"]

    def test_fallback_on_missing(self, tmp_path):
        tpl = load_sa_template(tmp_path / "nonexistent.json")
        assert tpl["name"] == "situation-analysis-fallback"

    def test_loads_custom_template(self, tmp_path):
        custom = tmp_path / "custom_sa.json"
        custom.write_text(json.dumps({
            "name": "test-sa",
            "sections": {"executive_summary": "Test Exec"},
            "limits": {},
        }), encoding="utf-8")
        tpl = load_sa_template(custom)
        assert tpl["name"] == "test-sa"


# ── Markdown rendering ───────────────────────────────────────────────


class TestRenderSituationAnalysis:
    def test_basic_render(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(
            graph_context=ctx,
            title="Test Situation Analysis",
            event_name="Cyclone Gezani-26",
            event_type="Cyclone/storm",
            period="2-6 March 2026",
            admin_hierarchy=_sample_hierarchy(),
        )
        assert "# Test Situation Analysis" in md
        assert "## Executive Summary" in md
        assert "Cyclone Gezani-26" in md
        assert "## National Impact Overview" in md
        assert "## Province-Level (Admin 1) Impact Summary" in md
        assert "## District-Level (Admin 2) Detailed Impact Tables" in md
        assert "## Shelter" in md or "## Shelter & Housing" in md
        assert "## Forecast & Risk Outlook" in md
        assert "## Sources and References" in md

    def test_has_event_card(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(
            graph_context=ctx,
            event_name="Cyclone Gezani-26",
            event_type="Cyclone/storm",
            admin_hierarchy=_sample_hierarchy(),
        )
        assert "### Event Card" in md
        assert "Cyclone Gezani-26" in md
        assert "Cyclone/storm" in md

    def test_has_key_figures(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(
            graph_context=ctx,
            admin_hierarchy=_sample_hierarchy(),
        )
        assert "### Key Figures" in md
        assert "Deaths" in md

    def test_has_admin1_table(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(
            graph_context=ctx,
            admin_hierarchy=_sample_hierarchy(),
        )
        assert "Province" in md
        assert "Zambezia" in md or "zambezia" in md.lower()

    def test_has_admin2_tables(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(
            graph_context=ctx,
            admin_hierarchy=_sample_hierarchy(),
        )
        # Should have sub-headings for provinces
        assert "### Zambezia" in md or "### Sofala" in md

    def test_has_citations(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(graph_context=ctx)
        assert "reliefweb.int" in md

    def test_has_annex(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(
            graph_context=ctx,
            admin_hierarchy=_sample_hierarchy(),
        )
        assert "Annex" in md

    def test_empty_evidence(self):
        ctx = {"evidence": [], "meta": {"cycles_analyzed": 0}}
        md = render_situation_analysis(graph_context=ctx)
        assert "# Situation Analysis" in md
        assert "Executive Summary" in md

    def test_sectoral_sections_present(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(graph_context=ctx)
        for sector in ["WASH", "Health", "Protection", "Education"]:
            assert sector in md

    def test_forecast_section(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(graph_context=ctx)
        assert "48-72 hour outlook" in md or "Forecast" in md

    def test_outstanding_needs(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(graph_context=ctx)
        assert "Outstanding Needs" in md

    def test_ai_assisted_banner(self):
        ctx = _sample_graph_context()
        md = render_situation_analysis(
            graph_context=ctx,
            use_llm=True,  # won't actually call LLM without key
        )
        # Without API key, falls back to deterministic
        assert "Situation Analysis" in md


# ── Component renderers ──────────────────────────────────────────────


class TestComponentRenderers:
    def _make_ontology(self) -> HumanitarianOntologyGraph:
        g = HumanitarianOntologyGraph()
        g.add_geo("TestCountry", admin_level=0)
        g.add_geo("ProvinceA", admin_level=1, parent="TestCountry")
        g.add_hazard("flood", HazardCategory.HYDROLOGICAL, "flood")
        g.add_impact(ImpactObservation(
            description="test",
            impact_type=ImpactType.PEOPLE,
            geo_area="ProvinceA",
            admin_level=1,
            severity_phase=3,
            figures={"deaths": 10, "displaced": 500},
        ))
        return g

    def test_event_card_render(self):
        g = self._make_ontology()
        lines: list[str] = []
        _render_event_card(
            lines,
            event_name="Flood Event",
            event_type="Flood",
            period="Jan 2026",
            ontology=g,
            meta={"by_country": {"TestCountry": 1}},
        )
        text = "\n".join(lines)
        assert "Flood Event" in text
        assert "Event Card" in text

    def test_key_figures_render(self):
        lines: list[str] = []
        _render_key_figures(
            lines,
            nat_figures={"deaths": 10, "displaced": 500},
            max_severity=3,
        )
        text = "\n".join(lines)
        assert "10" in text
        assert "500" in text
        assert "Severity Phase" in text

    def test_national_impact_table(self):
        lines: list[str] = []
        _render_national_impact_table(
            lines,
            nat_figures={"deaths": 10},
            template={"national_impact_table": {"rows": ["Deaths", "Missing"]}},
        )
        text = "\n".join(lines)
        assert "Deaths" in text
        assert "10" in text

    def test_admin1_table_empty(self):
        lines: list[str] = []
        _render_admin1_table(lines, admin1_agg={}, template={})
        text = "\n".join(lines)
        assert "No province-level data" in text

    def test_build_admin2_row(self):
        cols = ["District", "Deaths", "Displaced"]
        row = _build_admin2_row("TestDistrict", {"deaths": 5}, cols)
        assert row[0] == "TestDistrict"
        assert "5" in row[1]

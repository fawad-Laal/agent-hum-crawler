"""Tests for graph_ontology module."""

from __future__ import annotations

import pytest

from agent_hum_crawler.graph_ontology import (
    GeoArea,
    HazardCategory,
    HazardNode,
    HumanitarianOntologyGraph,
    ImpactObservation,
    ImpactType,
    NeedStatement,
    NeedType,
    ResponseActivity,
    RiskStatement,
    SourceClaim,
    build_ontology_from_evidence,
    _extract_figures,
    _classify_impact_type,
    _classify_need_types,
    _severity_from_text,
    _detect_sub_hazards,
    _map_severity_to_phase,
)


# ── Graph construction ───────────────────────────────────────────────


def _make_graph() -> HumanitarianOntologyGraph:
    g = HumanitarianOntologyGraph()
    g.add_geo("Mozambique", admin_level=0)
    g.add_geo("Zambezia", admin_level=1, parent="Mozambique")
    g.add_geo("Sofala", admin_level=1, parent="Mozambique")
    g.add_geo("Mocuba", admin_level=2, parent="Zambezia")
    g.add_geo("Quelimane", admin_level=2, parent="Zambezia")
    g.add_geo("Beira", admin_level=2, parent="Sofala")
    g.add_hazard(
        "Tropical Cyclone Gezani-26",
        category=HazardCategory.METEOROLOGICAL,
        specific_type="cyclone/storm",
        sub_hazards=["high winds", "storm surge"],
    )
    g.add_impact(ImpactObservation(
        description="52 deaths confirmed in Zambezia",
        impact_type=ImpactType.PEOPLE,
        geo_area="Zambezia",
        admin_level=1,
        severity_phase=4,
        figures={"deaths": 52, "displaced": 16000},
        source_url="https://example.com/1",
    ))
    g.add_impact(ImpactObservation(
        description="Houses destroyed in Mocuba",
        impact_type=ImpactType.HOUSING,
        geo_area="Mocuba",
        admin_level=2,
        severity_phase=3,
        figures={"houses_affected": 4200},
    ))
    g.add_impact(ImpactObservation(
        description="Bridge collapse on EN1",
        impact_type=ImpactType.INFRASTRUCTURE,
        geo_area="Beira",
        admin_level=2,
        severity_phase=3,
        figures={},
    ))
    g.add_need(NeedStatement(
        description="Food insecurity rising in Zambezia",
        need_type=NeedType.FOOD_SECURITY,
        geo_area="Zambezia",
        admin_level=1,
        severity_phase=3,
    ))
    g.add_need(NeedStatement(
        description="WASH contamination in Mocuba",
        need_type=NeedType.WASH,
        geo_area="Mocuba",
        admin_level=2,
        severity_phase=4,
    ))
    g.add_risk(RiskStatement(
        description="Flooding expected to worsen in 48h",
        hazard_name="flood",
        geo_area="Zambezia",
        horizon="48h",
    ))
    g.add_risk(RiskStatement(
        description="Cholera risk in 7 days",
        hazard_name="cholera",
        geo_area="Sofala",
        horizon="7d",
    ))
    g.add_response(ResponseActivity(
        description="WFP distributing food",
        actor="WFP",
        actor_type="un_agency",
        geo_area="Zambezia",
        sector="food_security",
    ))
    g.add_claim(SourceClaim(
        claim_text="52 deaths in Zambezia from cyclone",
        source_url="https://example.com/1",
        source_label="ReliefWeb",
        connector="reliefweb",
    ))
    return g


class TestGraphConstruction:
    def test_geo_hierarchy(self):
        g = _make_graph()
        admin1 = g.admin1_areas()
        assert len(admin1) == 2
        names = {a.name for a in admin1}
        assert "Zambezia" in names
        assert "Sofala" in names

    def test_admin2_under_parent(self):
        g = _make_graph()
        d = g.admin2_areas(parent="Zambezia")
        assert len(d) == 2
        names = {a.name for a in d}
        assert "Mocuba" in names
        assert "Quelimane" in names

    def test_children_of(self):
        g = _make_graph()
        children = g.children_of("Zambezia")
        assert len(children) == 2

    def test_hazard_added(self):
        g = _make_graph()
        assert len(g.hazards) == 1
        h = list(g.hazards.values())[0]
        assert h.category == HazardCategory.METEOROLOGICAL
        assert "high winds" in h.sub_hazards

    def test_no_duplicate_geo(self):
        g = HumanitarianOntologyGraph()
        g.add_geo("Test", admin_level=0)
        g.add_geo("Test", admin_level=0)
        assert len(g.geo_areas) == 1


class TestGraphQueries:
    def test_impacts_by_geo(self):
        g = _make_graph()
        impacts = g.impacts_by_geo("Zambezia")
        assert len(impacts) == 1
        assert impacts[0].figures["deaths"] == 52

    def test_impacts_by_type(self):
        g = _make_graph()
        housing = g.impacts_by_type(ImpactType.HOUSING)
        assert len(housing) == 1
        assert housing[0].geo_area == "Mocuba"

    def test_needs_by_sector(self):
        g = _make_graph()
        wash = g.needs_by_sector(NeedType.WASH)
        assert len(wash) == 1

    def test_needs_by_geo(self):
        g = _make_graph()
        needs = g.needs_by_geo("Zambezia")
        assert len(needs) == 1
        assert needs[0].need_type == NeedType.FOOD_SECURITY

    def test_risks_by_horizon(self):
        g = _make_graph()
        short = g.risks_by_horizon("48h")
        assert len(short) == 1
        medium = g.risks_by_horizon("7d")
        assert len(medium) == 1

    def test_responses_by_geo(self):
        g = _make_graph()
        resp = g.responses_by_geo("Zambezia")
        assert len(resp) == 1
        assert resp[0].actor == "WFP"

    def test_responses_by_sector(self):
        g = _make_graph()
        resp = g.responses_by_sector("food_security")
        assert len(resp) == 1

    def test_claims_for_geo(self):
        g = _make_graph()
        claims = g.claims_for_geo("Zambezia")
        assert len(claims) == 1


class TestAggregation:
    def test_national_figures(self):
        g = _make_graph()
        figs = g.national_figures()
        assert figs.get("deaths") == 52
        assert figs.get("displaced") == 16000
        assert figs.get("houses_affected") == 4200

    def test_max_severity(self):
        g = _make_graph()
        assert g.max_national_severity() == 4

    def test_admin1_aggregation(self):
        g = _make_graph()
        agg = g.aggregate_figures_by_admin1()
        assert "zambezia" in agg
        zambezia = agg["zambezia"]
        assert zambezia["figures"]["deaths"] == 52
        assert "Mocuba" in zambezia["districts_affected"]

    def test_admin2_aggregation(self):
        g = _make_graph()
        agg = g.aggregate_figures_by_admin2(admin1="Zambezia")
        assert "mocuba" in agg
        assert agg["mocuba"]["figures"]["houses_affected"] == 4200

    def test_sector_summary(self):
        g = _make_graph()
        summary = g.sector_summary()
        assert "food_security" in summary
        assert summary["food_security"]["count"] == 1
        assert "wash" in summary
        assert summary["wash"]["max_severity"] == 4

    def test_empty_graph_aggregation(self):
        g = HumanitarianOntologyGraph()
        assert g.national_figures() == {}
        assert g.max_national_severity() == 0
        assert g.aggregate_figures_by_admin1() == {}


class TestTextExtraction:
    def test_extract_figures_deaths(self):
        text = "There were 52 deaths and 16,000 displaced people"
        figs = _extract_figures(text)
        assert figs["deaths"] == 52
        assert figs["displaced"] == 16000

    def test_extract_figures_houses(self):
        text = "4,200 houses were destroyed"
        figs = _extract_figures(text)
        assert figs["houses_affected"] == 4200

    def test_extract_figures_empty(self):
        figs = _extract_figures("No numbers here")
        assert figs == {}

    def test_classify_impact_people(self):
        assert _classify_impact_type("52 deaths and 100 injured") == ImpactType.PEOPLE

    def test_classify_impact_housing(self):
        assert _classify_impact_type("houses destroyed and shelter needs") == ImpactType.HOUSING

    def test_classify_impact_infra(self):
        assert _classify_impact_type("bridge collapsed and road blocked") == ImpactType.INFRASTRUCTURE

    def test_classify_needs(self):
        needs = _classify_need_types("food insecurity and water contamination")
        assert NeedType.FOOD_SECURITY in needs
        assert NeedType.WASH in needs

    def test_severity_from_text(self):
        assert _severity_from_text("state of emergency declared") == 4
        assert _severity_from_text("catastrophic damage") == 5
        assert _severity_from_text("moderate flooding") == 2
        assert _severity_from_text("normal conditions") == 1

    def test_detect_sub_hazards(self):
        subs = _detect_sub_hazards("high winds and storm surge with flash flood")
        assert "high winds" in subs
        assert "storm surge" in subs
        assert "flash flood" in subs

    def test_map_severity_to_phase(self):
        assert _map_severity_to_phase("low") == 1
        assert _map_severity_to_phase("medium") == 2
        assert _map_severity_to_phase("high") == 3
        assert _map_severity_to_phase("critical") == 4


class TestBuildOntologyFromEvidence:
    def test_basic_evidence(self):
        evidence = [
            {
                "country": "Mozambique",
                "disaster_type": "cyclone/storm",
                "title": "Cyclone hits Mozambique",
                "summary": "52 deaths and 16000 displaced by cyclone",
                "text": "",
                "url": "https://example.com/1",
                "connector": "reliefweb",
                "severity": "high",
                "confidence": "high",
                "source_label": "ReliefWeb",
            },
        ]
        graph = build_ontology_from_evidence(evidence)
        assert len(graph.impacts) == 1
        assert len(graph.claims) == 1
        assert "mozambique" in graph.geo_areas
        figs = graph.national_figures()
        assert figs.get("deaths") == 52

    def test_with_admin_hierarchy(self):
        evidence = [
            {
                "country": "Mozambique",
                "disaster_type": "flood",
                "title": "Floods in Zambezia",
                "summary": "Severe flooding in Mocuba district",
                "text": "Mocuba district has 200 houses damaged",
                "url": "https://example.com/2",
                "connector": "government_feeds",
                "severity": "medium",
                "confidence": "medium",
                "source_label": "INGD",
            },
        ]
        hierarchy = {
            "Zambezia": ["Mocuba", "Quelimane"],
            "Sofala": ["Beira"],
        }
        graph = build_ontology_from_evidence(
            evidence, admin_hierarchy=hierarchy
        )
        assert "zambezia" in graph.geo_areas
        assert "mocuba" in graph.geo_areas
        # Impact should be assigned to Mocuba (detected from text)
        assert graph.impacts[0].geo_area == "Mocuba"
        assert graph.impacts[0].admin_level == 2

    def test_empty_evidence(self):
        graph = build_ontology_from_evidence([])
        assert len(graph.impacts) == 0
        assert len(graph.claims) == 0

    def test_risk_detection(self):
        evidence = [
            {
                "country": "Sri Lanka",
                "disaster_type": "cyclone/storm",
                "title": "Cyclone forecast",
                "summary": "Rainfall forecast predicts severe flooding expected in 7-day outlook",
                "text": "",
                "url": "https://example.com/3",
                "connector": "un_humanitarian_feeds",
                "severity": "medium",
                "confidence": "medium",
                "source_label": "OCHA",
            },
        ]
        graph = build_ontology_from_evidence(evidence)
        assert len(graph.risks) >= 1
        assert graph.risks[0].horizon == "7d"

    def test_response_detection(self):
        evidence = [
            {
                "country": "Mozambique",
                "disaster_type": "flood",
                "title": "UNICEF response",
                "summary": "UNICEF distributes supplies to flood-affected schools",
                "text": "",
                "url": "https://example.com/4",
                "connector": "un_humanitarian_feeds",
                "severity": "medium",
                "confidence": "high",
                "source_label": "UNICEF",
            },
        ]
        graph = build_ontology_from_evidence(evidence)
        assert len(graph.responses) >= 1
        assert graph.responses[0].actor_type == "un_agency"

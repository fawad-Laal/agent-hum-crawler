"""Tests for SA quality gate (Phase 3 — Task 3.4)."""

from __future__ import annotations

from agent_hum_crawler.sa_quality_gate import (
    SAQualityResult,
    quality_summary_markdown,
    score_situation_analysis,
)

# ── Minimal SA markdown fixture ──────────────────────────────────────

_MINIMAL_SA = """\
# Situation Analysis

Generated: 2026-02-20 00:00 UTC

## Executive Summary

### Event Card

| Field | Value |
|-------|-------|
| **Event** | Test Cyclone |

### Key Figures

| Figure | National Total |
|--------|---------------|
| **affected** | 120,000 |
| **displaced** | 45,000 |
| **deaths** | 23 |

Some executive summary text with a citation [1].

## National Impact Overview

| Figure | Value | As Of |
|--------|-------|-------|
| **affected** | 120,000 | as of 2026-02-18 |
| **displaced** | 45,000 | as of 2026-02-18 |
| **deaths** | 23 | as of 2026-02-17 |

National narrative paragraph here [1] [2].

## Province-Level (Admin 1) Impact Summary

| # | Province | Affected | Displaced |
|---|----------|----------|-----------|
| 1 | Maputo | 40,000 | 15,000 |
| 2 | Gaza | 30,000 | 10,000 |
| 3 | Inhambane | 25,000 | 8,000 |
| 4 | Sofala | 15,000 | 7,000 |
| 5 | Zambezia | 10,000 | 5,000 |

## District-Level (Admin 2) Detailed Impact Tables

Some district detail text.

## Shelter & Housing

Shelter narrative with citations [1] [3].

## Water, Sanitation & Hygiene (WASH)

WASH narrative text [2].

## Health

Health narrative text [1].

## Food Security, Nutrition & Livelihoods

Food security narrative text with reference [2] [3].

## Protection

Protection narrative text.

## Education

Education narrative text [1].

## Access Constraints

Some access constraint data.

## Outstanding Needs & Gaps

Gap analysis text [2].

## Forecast & Risk Outlook

Forecast paragraph.

## Annex — Full Admin 1 & Admin 2 Reference List

Admin reference data.

## Sources and References

1. https://reliefweb.int/report/1
2. https://bbc.com/news/2
3. https://example.com/report/3
"""


def test_score_full_sa_passes():
    citation_numbers = {
        "https://reliefweb.int/report/1": 1,
        "https://bbc.com/news/2": 2,
        "https://example.com/report/3": 3,
    }
    result = score_situation_analysis(
        _MINIMAL_SA,
        citation_numbers=citation_numbers,
    )
    assert isinstance(result, SAQualityResult)
    assert result.overall_score > 0.0
    # All sections present → high section completeness
    assert result.section_completeness > 0.8
    # Has valid citations
    assert result.citation_accuracy == 1.0
    # Has key figures
    assert result.key_figure_coverage > 0.0
    # Overall should be decent
    assert result.overall_score >= 0.4


def test_score_empty_sa_fails():
    result = score_situation_analysis("# Empty SA\n\nNothing here.\n")
    assert result.section_completeness == 0.0
    assert result.overall_score < 0.3
    assert not result.passed


def test_invalid_citations_reduce_accuracy():
    # Inject bad citation references
    md = _MINIMAL_SA.replace("[1]", "[99]")
    citation_numbers = {
        "https://reliefweb.int/report/1": 1,
        "https://bbc.com/news/2": 2,
        "https://example.com/report/3": 3,
    }
    result = score_situation_analysis(md, citation_numbers=citation_numbers)
    # Some citations are now invalid
    assert result.citation_accuracy < 1.0


def test_quality_summary_markdown():
    result = SAQualityResult(
        section_completeness=0.9,
        key_figure_coverage=0.6,
        citation_accuracy=1.0,
        citation_density=2.0,
        admin_coverage=0.8,
        date_attribution=0.5,
        overall_score=0.75,
        passed=True,
        thresholds={
            "section_completeness_min": 0.7,
            "key_figure_coverage_min": 0.3,
            "citation_accuracy_min": 0.8,
            "citation_density_min": 0.5,
            "admin_coverage_min": 0.2,
            "date_attribution_min": 0.3,
            "overall_pass_threshold": 0.55,
        },
    )
    md = quality_summary_markdown(result)
    assert "PASS" in md
    assert "0.75" in md
    assert "Section Completeness" in md


def test_custom_thresholds():
    result = score_situation_analysis(
        _MINIMAL_SA,
        thresholds={"overall_pass_threshold": 0.99},
    )
    # With very strict threshold, should fail
    assert not result.passed


def test_score_with_parsed_citations():
    """When no citation_numbers dict is given, the gate parses them from the Citations section."""
    result = score_situation_analysis(_MINIMAL_SA)
    assert result.citation_accuracy > 0.0
    assert result.details["citation_accuracy"]["known_citation_numbers"] >= 1

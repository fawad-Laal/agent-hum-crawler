"""Tests for source_credibility module (Phase 3 — Task 3.3)."""

from __future__ import annotations

from agent_hum_crawler.source_credibility import (
    annotate_evidence,
    credibility_weight,
    source_tier,
    tier_distribution,
    tier_label,
)


# ── source_tier ──────────────────────────────────────────────────────


def test_tier1_by_connector():
    assert source_tier(connector="reliefweb") == 1
    assert source_tier(connector="ocha") == 1


def test_tier2_by_connector():
    assert source_tier(connector="fews") == 2
    assert source_tier(connector="unicef") == 2
    assert source_tier(connector="government_feeds") == 2


def test_tier3_by_connector():
    assert source_tier(connector="bbc") == 3
    assert source_tier(connector="reuters") == 3


def test_tier4_fallback():
    assert source_tier(connector="unknown_blog") == 4


def test_tier_by_domain():
    assert source_tier(connector="", domain="reliefweb.int") == 1
    assert source_tier(connector="", domain="fews.net") == 2
    assert source_tier(connector="", domain="bbc.com") == 3
    assert source_tier(connector="", domain="randomblog.example.com") == 4


def test_tier_by_source_type():
    assert source_tier(connector="", source_type="un") == 1
    assert source_tier(connector="", source_type="government") == 2
    assert source_tier(connector="", source_type="news") == 3
    assert source_tier(connector="", source_type="social_media") == 4


# ── tier_label / credibility_weight ──────────────────────────────────


def test_tier_labels():
    assert "UN" in tier_label(1) or "Authoritative" in tier_label(1)
    assert isinstance(tier_label(4), str)


def test_credibility_weights():
    assert credibility_weight(1) == 2.0
    assert credibility_weight(2) == 1.5
    assert credibility_weight(3) == 1.0
    assert credibility_weight(4) == 0.7
    # Unknown tier defaults to tier-4 weight
    assert credibility_weight(99) == 0.7


# ── annotate_evidence ────────────────────────────────────────────────


def test_annotate_evidence_adds_fields():
    evidence = [
        {"connector": "reliefweb", "source_type": "un", "url": "https://reliefweb.int/report/1"},
        {"connector": "bbc", "source_type": "news", "url": "https://bbc.com/news/1"},
        {"connector": "unknown", "source_type": "", "url": ""},
    ]
    annotate_evidence(evidence)
    assert evidence[0]["credibility_tier"] == 1
    assert evidence[0]["credibility_weight"] == 2.0
    assert evidence[1]["credibility_tier"] == 3
    assert evidence[1]["credibility_weight"] == 1.0
    assert evidence[2]["credibility_tier"] == 4


# ── tier_distribution ────────────────────────────────────────────────


def test_tier_distribution():
    evidence = [
        {"credibility_tier": 1},
        {"credibility_tier": 1},
        {"credibility_tier": 2},
        {"credibility_tier": 3},
    ]
    dist = tier_distribution(evidence)
    assert dist["tier_1"] == 2
    assert dist["tier_2"] == 1
    assert dist["tier_3"] == 1
    assert dist["tier_4"] == 0

"""Source credibility tier system for humanitarian intelligence.

Assigns credibility tiers (1-4) to evidence sources based on their
connector and source type.  Higher tiers indicate more authoritative
sources.  Used for:
  - Figure confidence weighting in the ontology
  - Evidence ranking in reporting and SA
  - Quality gate scoring

Tier Definitions
~~~~~~~~~~~~~~~~
  Tier 1 — UN & OCHA (highest authority)
  Tier 2 — International NGOs, government agencies, clusters
  Tier 3 — Major international news organisations
  Tier 4 — Local news, aggregators, social media (lowest)
"""

from __future__ import annotations

from typing import Any

# ── Tier definitions ─────────────────────────────────────────────────
# Each entry maps connector name (or prefix) or domain to a tier.
# Lower tier number = higher credibility.

TIER_1_CONNECTORS = frozenset({
    "reliefweb",
    "ocha",
    "un_ocha",
    "unocha",
    "humanitarian_response",
})

TIER_2_CONNECTORS = frozenset({
    "government_feeds",
    "government",
    "fews",
    "fews_net",
    "care_news",
    "care",
    "icrc",
    "ifrc",
    "msf",
    "unicef",
    "unhcr",
    "wfp",
    "who",
    "iom",
    "gdacs",
    "usgs",
})

TIER_3_CONNECTORS = frozenset({
    "bbc",
    "reuters",
    "guardian",
    "nyt",
    "npr",
    "aljazeera",
    "al_jazeera",
    "africanews",
    "allafricamedia",
    "allafrica",
    "ana",
})

# Tier 4 is the default for anything not in tiers 1-3.

TIER_1_DOMAINS = frozenset({
    "reliefweb.int",
    "unocha.org",
    "humanitarian.response.info",
    "fts.unocha.org",
    "data.humdata.org",
})

TIER_2_DOMAINS = frozenset({
    "fews.net",
    "care.org",
    "icrc.org",
    "ifrc.org",
    "msf.org",
    "unicef.org",
    "unhcr.org",
    "wfp.org",
    "who.int",
    "iom.int",
    "gdacs.org",
    "earthquake.usgs.gov",
})

TIER_3_DOMAINS = frozenset({
    "bbc.com", "bbc.co.uk",
    "reuters.com",
    "theguardian.com",
    "nytimes.com",
    "npr.org",
    "aljazeera.com",
    "africanews.com",
    "allafrica.com",
})


# ── Tier resolution ──────────────────────────────────────────────────

def source_tier(
    connector: str = "",
    source_type: str = "",
    domain: str = "",
) -> int:
    """Return credibility tier (1-4) for a source.

    Parameters
    ----------
    connector : str
        Connector name (e.g. ``"reliefweb"``).
    source_type : str
        Source type (``"official"``/``"humanitarian"``/``"news"``/``"social"``).
    domain : str
        URL domain (e.g. ``"reliefweb.int"``).

    Returns
    -------
    int
        1 (highest), 2, 3, or 4 (lowest).
    """
    c = connector.strip().lower()
    d = domain.strip().lower()
    st = source_type.strip().lower()

    # Check connector name first (fastest path)
    if c in TIER_1_CONNECTORS:
        return 1
    if c in TIER_2_CONNECTORS:
        return 2
    if c in TIER_3_CONNECTORS:
        return 3

    # Check domain
    if d in TIER_1_DOMAINS:
        return 1
    if d in TIER_2_DOMAINS:
        return 2
    if d in TIER_3_DOMAINS:
        return 3

    # Fallback by source_type
    if st in ("official", "un", "un_agency", "ingo"):
        return 1
    if st in ("humanitarian", "government", "ngo"):
        return 2
    if st in ("news", "media"):
        return 3
    if st in ("social", "social_media", "blog"):
        return 4

    return 4


def tier_label(tier: int) -> str:
    """Human-readable label for a credibility tier."""
    return {
        1: "UN/OCHA (Tier 1)",
        2: "NGO/Government (Tier 2)",
        3: "Major News (Tier 3)",
        4: "Other (Tier 4)",
    }.get(tier, f"Tier {tier}")


def credibility_weight(tier: int) -> float:
    """Return a numeric weight for evidence scoring.

    Tier 1 evidence is weighted 2.0×, Tier 2 at 1.5×, Tier 3 at 1.0×,
    Tier 4 at 0.7×.
    """
    return {1: 2.0, 2: 1.5, 3: 1.0, 4: 0.7}.get(tier, 0.7)


# ── Bulk helpers ─────────────────────────────────────────────────────

def annotate_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add ``credibility_tier`` and ``credibility_weight`` to each evidence item."""
    from urllib.parse import urlparse

    for ev in evidence:
        connector = str(ev.get("connector", ""))
        source_type = str(ev.get("source_type", ""))
        url = str(ev.get("canonical_url") or ev.get("url", ""))
        domain = urlparse(url).netloc.lower() if url else ""

        tier = source_tier(connector=connector, source_type=source_type, domain=domain)
        ev["credibility_tier"] = tier
        ev["credibility_weight"] = credibility_weight(tier)
    return evidence


def tier_distribution(evidence: list[dict[str, Any]]) -> dict[str, int]:
    """Return count of evidence items in each tier."""
    counts: dict[str, int] = {"tier_1": 0, "tier_2": 0, "tier_3": 0, "tier_4": 0}
    for ev in evidence:
        tier = ev.get("credibility_tier", 4)
        counts[f"tier_{tier}"] = counts.get(f"tier_{tier}", 0) + 1
    return counts

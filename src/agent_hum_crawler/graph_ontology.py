"""Humanitarian ontology graph for structured evidence retrieval.

Implements the Graph RAG ontology for humanitarian crisis analysis:

  Response Ontology   ──  Actor (NGO, Agency, Government, RedCo, Cluster)
                           └── implements → Response Activity
                                └── delivered in → Geo Area

  Population Ontology ──  Population Group
                           ├── measured by → Population Measure
                           └── status → Population Status

  Impact Ontology     ──  Impact Observation
                           ├── of type → Impact Type
                           │     (People, Systems, Services, Infrastructure,
                           │      Housing & LC)
                           └── affects → Population Group
                           └── located in → Geo Area

  Needs Ontology      ──  Need Statement
                           └── of type → Need Type
                                 (Food Security, Health, WASH, Protection,
                                  Education)
                           └── indicates → Impact Observation

  Hazard Ontology     ──  Hazard
                           ├── subtypes: Meteorological, Hydrological,
                           │   Climatological, Conflict, Health
                           └── causes risk of → Risk Statement
                                └── concerns → Population Group

  Evidence            ──  Claim
                           └── supported by → Source Document

  Geo Area            ──  GPS Location | ADM Location | Context Snapshot
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

_log = logging.getLogger(__name__)

# ── Optional Rust acceleration ───────────────────────────────────────
_USE_RUST = False
_USE_RUST_FIGURES = False
try:
    from .rust_accel import (
        extract_figures as _rust_extract_figures,
        classify_impact_type as _rust_classify_impact_type,
        classify_need_types as _rust_classify_need_types,
        severity_from_text as _rust_severity_from_text,
        is_risk_text as _rust_is_risk_text,
        detect_response_actor as _rust_detect_response_actor,
        similarity_ratio as _rust_similarity_ratio,
        rust_available,
    )
    _USE_RUST = rust_available()
    _USE_RUST_FIGURES = _USE_RUST
    if _USE_RUST:
        _log.info("graph_ontology: Rust acceleration enabled (figures + classify + detect)")
except ImportError:
    pass


# ── Enums ────────────────────────────────────────────────────────────

class HazardCategory(str, Enum):
    METEOROLOGICAL = "meteorological"
    HYDROLOGICAL = "hydrological"
    CLIMATOLOGICAL = "climatological"
    GEOPHYSICAL = "geophysical"
    CONFLICT = "conflict"
    HEALTH = "health"


class ImpactType(str, Enum):
    PEOPLE = "people_impact"
    SYSTEMS = "systems_impact"
    SERVICES = "services_impact"
    INFRASTRUCTURE = "infrastructure_impact"
    HOUSING = "housing_lc_impact"


class NeedType(str, Enum):
    FOOD_SECURITY = "food_security"
    HEALTH = "health"
    WASH = "wash"
    PROTECTION = "protection"
    EDUCATION = "education"
    SHELTER = "shelter"
    NUTRITION = "nutrition"
    LOGISTICS = "logistics"
    EARLY_RECOVERY = "early_recovery"
    CAMP_MANAGEMENT = "camp_management"


class SeverityPhase(int, Enum):
    MINIMAL = 1
    STRESSED = 2
    CRISIS = 3
    EMERGENCY = 4
    CATASTROPHE = 5


# ── Graph Nodes ──────────────────────────────────────────────────────

@dataclass
class GeoArea:
    """Geographic area at any admin level."""
    name: str
    admin_level: int  # 0=country, 1=province, 2=district
    parent: str | None = None
    iso3: str = ""  # ISO-3166-1 alpha-3 (country-level only)
    gps_lat: float | None = None
    gps_lon: float | None = None


@dataclass
class HazardNode:
    """A hazard event or type."""
    name: str
    category: HazardCategory
    specific_type: str  # e.g. "cyclone/storm", "flood"
    sub_hazards: list[str] = field(default_factory=list)
    # e.g. ["high winds", "storm surge", "heavy rainfall"]


@dataclass
class ImpactObservation:
    """An observed impact at a location."""
    description: str
    impact_type: ImpactType
    geo_area: str
    admin_level: int
    severity_phase: int = 2
    figures: dict[str, Any] = field(default_factory=dict)
    # e.g. {"deaths": 52, "displaced": 16000}
    source_url: str = ""
    source_connector: str = ""
    confidence: str = "medium"
    # Temporal fields (Phase 2)
    reported_date: str = ""   # YYYY-MM-DD or ISO-8601 fragment
    source_label: str = ""
    # Credibility tier (Phase 3): 1=UN/OCHA, 2=NGO/Gov, 3=News, 4=Other
    credibility_tier: int = 4


@dataclass
class NeedStatement:
    """An identified humanitarian need."""
    description: str
    need_type: NeedType
    geo_area: str
    admin_level: int
    severity_phase: int = 2
    indicates_impact: str = ""
    source_url: str = ""
    # Temporal fields (Phase 2)
    reported_date: str = ""
    source_label: str = ""


@dataclass
class RiskStatement:
    """A forward-looking risk assessment."""
    description: str
    hazard_name: str
    geo_area: str
    horizon: str = "48h"  # "48h", "7d", "medium_term"
    probability: str = "likely"
    source_url: str = ""
    # Temporal fields (Phase 2)
    reported_date: str = ""
    source_label: str = ""


@dataclass
class ResponseActivity:
    """A response action by an actor."""
    description: str
    actor: str
    actor_type: str  # "ngo", "un_agency", "government", "cluster"
    geo_area: str
    sector: str = ""
    source_url: str = ""


@dataclass
class SourceClaim:
    """An evidence claim backed by a source document."""
    claim_text: str
    source_url: str
    source_label: str
    connector: str
    published_at: str | None = None
    confidence: str = "medium"
    credibility_tier: int = 4


# ── Ontology Graph ───────────────────────────────────────────────────

@dataclass
class HumanitarianOntologyGraph:
    """In-memory graph holding all ontology nodes and edges.

    Designed for structured retrieval from evidence extracted by
    the crawler's event/raw-item pipeline.
    """

    geo_areas: dict[str, GeoArea] = field(default_factory=dict)
    hazards: dict[str, HazardNode] = field(default_factory=dict)
    impacts: list[ImpactObservation] = field(default_factory=list)
    needs: list[NeedStatement] = field(default_factory=list)
    risks: list[RiskStatement] = field(default_factory=list)
    responses: list[ResponseActivity] = field(default_factory=list)
    claims: list[SourceClaim] = field(default_factory=list)

    # ── Construction helpers ──────────────────────────────────

    def add_geo(
        self,
        name: str,
        admin_level: int,
        parent: str | None = None,
        iso3: str = "",
    ) -> GeoArea:
        key = name.strip().lower()
        if key not in self.geo_areas:
            self.geo_areas[key] = GeoArea(
                name=name.strip(),
                admin_level=admin_level,
                parent=parent.strip().lower() if parent else None,
                iso3=iso3,
            )
        elif iso3 and not self.geo_areas[key].iso3:
            # Back-fill ISO3 if it wasn't set on first insertion
            self.geo_areas[key].iso3 = iso3
        return self.geo_areas[key]

    def add_hazard(
        self,
        name: str,
        category: HazardCategory,
        specific_type: str,
        sub_hazards: list[str] | None = None,
    ) -> HazardNode:
        key = name.strip().lower()
        if key not in self.hazards:
            self.hazards[key] = HazardNode(
                name=name.strip(),
                category=category,
                specific_type=specific_type.strip().lower(),
                sub_hazards=sub_hazards or [],
            )
        return self.hazards[key]

    def add_impact(self, obs: ImpactObservation) -> None:
        self.impacts.append(obs)

    def add_need(self, need: NeedStatement) -> None:
        self.needs.append(need)

    def add_risk(self, risk: RiskStatement) -> None:
        self.risks.append(risk)

    def add_response(self, resp: ResponseActivity) -> None:
        self.responses.append(resp)

    def add_claim(self, claim: SourceClaim) -> None:
        self.claims.append(claim)

    # ── Query helpers ─────────────────────────────────────────

    def impacts_by_geo(
        self,
        geo_name: str,
        admin_level: int | None = None,
    ) -> list[ImpactObservation]:
        key = geo_name.strip().lower()
        results = [
            i for i in self.impacts
            if i.geo_area.strip().lower() == key
        ]
        if admin_level is not None:
            results = [
                i for i in results if i.admin_level == admin_level
            ]
        return sorted(
            results,
            key=lambda x: x.severity_phase,
            reverse=True,
        )

    def impacts_by_type(
        self, impact_type: ImpactType
    ) -> list[ImpactObservation]:
        return [i for i in self.impacts if i.impact_type == impact_type]

    def needs_by_sector(
        self, need_type: NeedType
    ) -> list[NeedStatement]:
        return [n for n in self.needs if n.need_type == need_type]

    def needs_by_geo(
        self,
        geo_name: str,
        admin_level: int | None = None,
    ) -> list[NeedStatement]:
        key = geo_name.strip().lower()
        results = [
            n for n in self.needs
            if n.geo_area.strip().lower() == key
        ]
        if admin_level is not None:
            results = [
                n for n in results if n.admin_level == admin_level
            ]
        return results

    def risks_by_horizon(
        self, horizon: str
    ) -> list[RiskStatement]:
        return [r for r in self.risks if r.horizon == horizon]

    def risks_by_geo(
        self, geo_name: str
    ) -> list[RiskStatement]:
        key = geo_name.strip().lower()
        return [
            r for r in self.risks
            if r.geo_area.strip().lower() == key
        ]

    def responses_by_geo(
        self, geo_name: str
    ) -> list[ResponseActivity]:
        key = geo_name.strip().lower()
        return [
            r for r in self.responses
            if r.geo_area.strip().lower() == key
        ]

    def responses_by_sector(
        self, sector: str
    ) -> list[ResponseActivity]:
        key = sector.strip().lower()
        return [
            r for r in self.responses
            if r.sector.strip().lower() == key
        ]

    def claims_for_geo(
        self, geo_name: str
    ) -> list[SourceClaim]:
        key = geo_name.strip().lower()
        return [
            c for c in self.claims
            if key in c.claim_text.lower()
        ]

    def children_of(
        self, parent_geo: str
    ) -> list[GeoArea]:
        key = parent_geo.strip().lower()
        return [
            g for g in self.geo_areas.values()
            if g.parent == key
        ]

    def admin1_areas(self) -> list[GeoArea]:
        return sorted(
            [g for g in self.geo_areas.values() if g.admin_level == 1],
            key=lambda g: g.name,
        )

    def admin2_areas(
        self, parent: str | None = None
    ) -> list[GeoArea]:
        areas = [
            g for g in self.geo_areas.values()
            if g.admin_level == 2
        ]
        if parent:
            key = parent.strip().lower()
            areas = [a for a in areas if a.parent == key]
        return sorted(areas, key=lambda g: g.name)

    # ── Aggregation helpers for situation analysis ────────────

    def aggregate_figures_by_admin1(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Aggregate impact figures by Admin 1 areas (deduplicated).

        Within each admin1 bucket, figures are grouped by
        (admin2_or_self_key, figure_key) and the *max* value kept,
        preventing double-counting from multiple sources.
        """
        agg: dict[str, dict[str, Any]] = {}
        # Track per-location figure maxima for dedup
        # admin1_key → {(geo_leaf, fig_key) → max_value}
        fig_dedup: dict[str, dict[tuple[str, str], int]] = {}

        for impact in self.impacts:
            geo_key = impact.geo_area.strip().lower()
            geo = self.geo_areas.get(geo_key)
            if not geo:
                continue
            if geo.admin_level == 1:
                admin1_key = geo_key
            elif geo.admin_level == 2 and geo.parent:
                admin1_key = geo.parent
            else:
                continue
            bucket = agg.setdefault(admin1_key, {
                "name": self.geo_areas.get(
                    admin1_key, GeoArea(admin1_key, 1)
                ).name,
                "figures": Counter(),
                "impact_count": 0,
                "max_severity": 0,
                "districts_affected": set(),
            })
            bucket["impact_count"] += 1
            # Dedup: track max per (leaf_geo, fig_key) within this admin1
            leaf_dedup = fig_dedup.setdefault(admin1_key, {})
            for k, v in impact.figures.items():
                if isinstance(v, (int, float)):
                    leaf_key = (geo_key, k)
                    leaf_dedup[leaf_key] = max(
                        leaf_dedup.get(leaf_key, 0), int(v)
                    )
            bucket["max_severity"] = max(
                bucket["max_severity"],
                impact.severity_phase,
            )
            if geo.admin_level == 2:
                bucket["districts_affected"].add(geo.name)

        # Rebuild figure totals from deduped maxima
        for admin1_key, bucket in agg.items():
            deduped_totals: Counter[str] = Counter()
            for (_, fig_key), val in fig_dedup.get(admin1_key, {}).items():
                deduped_totals[fig_key] += val
            bucket["figures"] = dict(deduped_totals)

        # Convert sets for serialisation
        for bucket in agg.values():
            bucket["districts_affected"] = sorted(
                bucket["districts_affected"]
            )
        return agg

    def aggregate_figures_by_admin2(
        self,
        admin1: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Aggregate impact figures by Admin 2 areas (deduplicated).

        For each district, the *max* value per figure key is kept
        across multiple impact observations to prevent double-counting.
        """
        agg: dict[str, dict[str, Any]] = {}
        # geo_key → {fig_key → max_value}
        fig_dedup: dict[str, dict[str, int]] = {}

        for impact in self.impacts:
            geo_key = impact.geo_area.strip().lower()
            geo = self.geo_areas.get(geo_key)
            if not geo or geo.admin_level != 2:
                continue
            if admin1 and geo.parent != admin1.strip().lower():
                continue
            bucket = agg.setdefault(geo_key, {
                "name": geo.name,
                "parent": geo.parent or "",
                "figures": Counter(),
                "impact_count": 0,
                "max_severity": 0,
            })
            bucket["impact_count"] += 1
            leaf_dedup = fig_dedup.setdefault(geo_key, {})
            for k, v in impact.figures.items():
                if isinstance(v, (int, float)):
                    leaf_dedup[k] = max(leaf_dedup.get(k, 0), int(v))
            bucket["max_severity"] = max(
                bucket["max_severity"],
                impact.severity_phase,
            )

        # Rebuild from deduped maxima
        for geo_key, bucket in agg.items():
            bucket["figures"] = dict(fig_dedup.get(geo_key, {}))
        return agg

    def sector_summary(self) -> dict[str, dict[str, Any]]:
        """Summarise needs by sector across all geos."""
        summary: dict[str, dict[str, Any]] = {}
        for need in self.needs:
            sector = need.need_type.value
            bucket = summary.setdefault(sector, {
                "count": 0,
                "max_severity": 0,
                "areas": set(),
                "descriptions": [],
            })
            bucket["count"] += 1
            bucket["max_severity"] = max(
                bucket["max_severity"],
                need.severity_phase,
            )
            bucket["areas"].add(need.geo_area)
            if need.description:
                bucket["descriptions"].append(
                    need.description[:200]
                )
        for bucket in summary.values():
            bucket["areas"] = sorted(bucket["areas"])
        return summary

    def national_figures(self) -> dict[str, int]:
        """Sum all impact figures at national level with deduplication.

        Figures are grouped by (geo_area, figure_key).  Within each
        group the *maximum* value is kept (not summed) to avoid counting
        the same statistic from multiple sources twice.  The per-
        location maxima are then summed to produce national totals.
        """
        # (geo_key, figure_key) → max value
        geo_fig: dict[tuple[str, str], int] = {}
        for impact in self.impacts:
            geo_key = impact.geo_area.strip().lower()
            for k, v in impact.figures.items():
                if isinstance(v, (int, float)):
                    bucket_key = (geo_key, k)
                    geo_fig[bucket_key] = max(
                        geo_fig.get(bucket_key, 0), int(v)
                    )
        # Sum the per-location maxima
        totals: Counter[str] = Counter()
        for (_, fig_key), val in geo_fig.items():
            totals[fig_key] += val
        return dict(totals)

    def national_figures_with_dates(self) -> dict[str, dict[str, Any]]:
        """Like ``national_figures`` but also returns the latest reported
        date and source for each figure key.

        Returns ``{fig_key: {"value": int, "as_of": str, "source": str}}``.
        """
        # (geo_key, fig_key) → (max_value, best_date, best_source)
        geo_fig: dict[tuple[str, str], tuple[int, str, str]] = {}
        for impact in self.impacts:
            geo_key = impact.geo_area.strip().lower()
            rd = impact.reported_date or ""
            sl = impact.source_label or ""
            for k, v in impact.figures.items():
                if isinstance(v, (int, float)):
                    bucket_key = (geo_key, k)
                    cur = geo_fig.get(bucket_key)
                    iv = int(v)
                    if cur is None or iv > cur[0] or (iv == cur[0] and rd > cur[1]):
                        geo_fig[bucket_key] = (iv, rd, sl)

        # Aggregate: sum values, keep latest date per fig_key
        agg: dict[str, dict[str, Any]] = {}
        for (_, fig_key), (val, rd, sl) in geo_fig.items():
            if fig_key not in agg:
                agg[fig_key] = {"value": 0, "as_of": rd, "source": sl}
            agg[fig_key]["value"] += val
            if rd > agg[fig_key]["as_of"]:
                agg[fig_key]["as_of"] = rd
                agg[fig_key]["source"] = sl
        return agg

    def max_national_severity(self) -> int:
        if not self.impacts:
            return 0
        return max(i.severity_phase for i in self.impacts)

    # ── Province-level figure distribution ────────────────────

    def distribute_national_figures(self) -> dict[str, dict[str, Any]]:
        """Distribute national-level figures to admin1 areas proportionally.

        When a figure is reported at admin-level 0 (country) but admin1
        areas are known from other evidence, the figure is split across
        those admin1 areas in proportion to their evidence-mention share.
        Figures already reported at admin1/admin2 level are kept as-is.

        Returns ``{admin1_key: {"name": ..., "figures": {...},
        "distributed": bool, "impact_count": int}}``.
        """
        # Step 1: count evidence mentions per admin1
        admin1_mention_count: Counter[str] = Counter()
        admin1_names: dict[str, str] = {}
        for impact in self.impacts:
            geo_key = impact.geo_area.strip().lower()
            geo = self.geo_areas.get(geo_key)
            if not geo:
                continue
            if geo.admin_level == 1:
                admin1_mention_count[geo_key] += 1
                admin1_names[geo_key] = geo.name
            elif geo.admin_level == 2 and geo.parent:
                admin1_mention_count[geo.parent] += 1
                parent_geo = self.geo_areas.get(geo.parent)
                if parent_geo:
                    admin1_names[geo.parent] = parent_geo.name

        # Step 2: aggregate already-localised figures (admin1 + admin2)
        localised = self.aggregate_figures_by_admin1()

        # Step 3: collect national-level figures (admin_level == 0)
        national_fig: dict[str, int] = {}
        for impact in self.impacts:
            if impact.admin_level != 0:
                continue
            for k, v in impact.figures.items():
                if isinstance(v, (int, float)):
                    national_fig[k] = max(national_fig.get(k, 0), int(v))

        # Step 4: distribute national figures to admin1 proportionally
        total_mentions = sum(admin1_mention_count.values())
        result: dict[str, dict[str, Any]] = {}

        # Seed from already-localised
        for a1_key, bucket in localised.items():
            result[a1_key] = {
                "name": bucket["name"],
                "figures": dict(bucket["figures"]),
                "distributed": False,
                "impact_count": bucket["impact_count"],
            }

        if total_mentions > 0 and national_fig:
            for a1_key, mentions in admin1_mention_count.items():
                proportion = mentions / total_mentions
                if a1_key not in result:
                    result[a1_key] = {
                        "name": admin1_names.get(a1_key, a1_key),
                        "figures": {},
                        "distributed": True,
                        "impact_count": mentions,
                    }
                for fig_key, nat_val in national_fig.items():
                    existing = result[a1_key]["figures"].get(fig_key, 0)
                    distributed_val = int(round(nat_val * proportion))
                    if distributed_val > existing:
                        result[a1_key]["figures"][fig_key] = distributed_val
                        result[a1_key]["distributed"] = True

        return result


# ── Builder: evidence → ontology graph ───────────────────────────────

# Keyword mappings for NLP-light extraction from evidence text.

_IMPACT_KEYWORDS: dict[ImpactType, list[str]] = {
    ImpactType.PEOPLE: [
        "deaths", "killed", "fatalities", "dead", "missing",
        "injured", "casualties", "displaced", "evacuated",
    ],
    ImpactType.HOUSING: [
        "houses destroyed", "houses damaged", "homes destroyed",
        "homes damaged", "housing", "shelter",
    ],
    ImpactType.INFRASTRUCTURE: [
        "bridge", "road", "highway", "port", "airport",
        "power", "electricity", "grid", "infrastructure",
    ],
    ImpactType.SERVICES: [
        "hospital", "health facility", "clinic", "school",
        "water supply", "sanitation",
    ],
    ImpactType.SYSTEMS: [
        "market", "supply chain", "food system", "agriculture",
        "fisheries", "livelihoods",
    ],
}

_NEED_KEYWORDS: dict[NeedType, list[str]] = {
    NeedType.FOOD_SECURITY: [
        "food", "hunger", "nutrition", "malnutrition",
        "famine", "food insecurity", "crop", "harvest",
    ],
    NeedType.HEALTH: [
        "health", "medical", "cholera", "malaria", "dengue",
        "disease", "epidemic", "outbreak", "medicine",
    ],
    NeedType.WASH: [
        "water", "sanitation", "hygiene", "wash",
        "contamination", "borehole", "latrine",
    ],
    NeedType.PROTECTION: [
        "protection", "gbv", "child protection",
        "trafficking", "violence",
    ],
    NeedType.EDUCATION: [
        "school", "education", "learner", "student",
        "teacher", "classroom",
    ],
    NeedType.SHELTER: [
        "shelter", "housing", "accommodation", "tent",
        "tarpaulin", "nfi",
    ],
    NeedType.LOGISTICS: [
        "logistics", "transport", "access", "road",
        "bridge", "supply",
    ],
}

_RISK_KEYWORDS = [
    "forecast", "outlook", "prediction", "warning",
    "alert", "expected", "anticipated", "risk",
    "likelihood", "probability", "projection",
]

_RESPONSE_ACTOR_KEYWORDS: dict[str, str] = {
    "un": "un_agency",
    "ocha": "un_agency",
    "unicef": "un_agency",
    "wfp": "un_agency",
    "who": "un_agency",
    "unhcr": "un_agency",
    "ifrc": "redco",
    "red cross": "redco",
    "red crescent": "redco",
    "government": "government",
    "ministry": "government",
    "national disaster": "government",
    "ingd": "government",
    "cenoe": "government",
    "ngo": "ngo",
    "care": "ngo",
    "oxfam": "ngo",
    "msf": "ngo",
    "save the children": "ngo",
    "cluster": "cluster",
}

HAZARD_CATEGORY_MAP: dict[str, HazardCategory] = {
    "cyclone/storm": HazardCategory.METEOROLOGICAL,
    "heatwave": HazardCategory.METEOROLOGICAL,
    "flood": HazardCategory.HYDROLOGICAL,
    "flash flood": HazardCategory.HYDROLOGICAL,
    "storm surge": HazardCategory.HYDROLOGICAL,
    "drought": HazardCategory.CLIMATOLOGICAL,
    "wildfire": HazardCategory.CLIMATOLOGICAL,
    "earthquake": HazardCategory.GEOPHYSICAL,
    "landslide": HazardCategory.GEOPHYSICAL,
    "tsunami": HazardCategory.GEOPHYSICAL,
    "conflict emergency": HazardCategory.CONFLICT,
    "armed conflict": HazardCategory.CONFLICT,
    "cholera": HazardCategory.HEALTH,
    "dengue": HazardCategory.HEALTH,
}


# ── Country admin gazetteers ─────────────────────────────────────────
# Used for auto-detecting admin1/admin2 areas from evidence text
# when no explicit admin_hierarchy is provided.

COUNTRY_GAZETTEERS: dict[str, dict[str, list[str]]] = {
    "madagascar": {
        "Analamanga": [
            "Antananarivo", "Ambohidratrimo", "Ankazobe",
            "Anjozorobe", "Manjakandriana", "Tsiroanomandidy",
        ],
        "Atsinanana": [
            "Toamasina", "Brickaville", "Mahanoro",
            "Vatomandry", "Marolambo", "Antanambao Manampotsy",
        ],
        "Vatovavy-Fitovinany": [
            "Mananjary", "Nosy Varika", "Ifanadiana",
            "Ikongo", "Manakara",
        ],
        "Atsimo-Atsinanana": [
            "Farafangana", "Vangaindrano", "Midongy du Sud",
            "Vondrozo", "Befotaka",
        ],
        "Boeny": [
            "Mahajanga", "Marovoay", "Mitsinjo",
            "Ambato-Boeni", "Soalala",
        ],
        "Diana": [
            "Antsiranana", "Nosy Be", "Ambanja",
            "Ambilobe", "Antsirabe Nord",
        ],
        "Sava": [
            "Sambava", "Antalaha", "Vohémar",
            "Andapa",
        ],
        "Menabe": [
            "Morondava", "Belo sur Tsiribihina",
            "Mahabo", "Miandrivazo", "Manja",
        ],
        "Atsimo-Andrefana": [
            "Toliara", "Sakaraha", "Ankazoabo",
            "Betioky", "Morombe", "Ampanihy",
        ],
        "Androy": [
            "Ambovombe", "Tsihombe", "Bekily",
            "Beloha",
        ],
        "Anosy": [
            "Taolagnaro", "Amboasary", "Betroka",
        ],
        "Vakinankaratra": [
            "Antsirabe", "Ambatolampy", "Betafo",
            "Faratsiho",
        ],
        "Analanjirofo": [
            "Fenoarivo Atsinanana", "Mananara Nord",
            "Maroantsetra", "Sainte-Marie",
        ],
        "Alaotra-Mangoro": [
            "Ambatondrazaka", "Moramanga",
            "Amparafaravola", "Andilamena",
        ],
        "Sofia": [
            "Antsohihy", "Port-Bergé", "Mampikony",
            "Bealanana", "Befandriana-Nord",
        ],
        "Betsiboka": [
            "Maevatanana", "Kandreho", "Tsaratanana",
        ],
        "Melaky": [
            "Maintirano", "Morafenobe", "Antsalova",
            "Ambatomainty", "Besalampy",
        ],
        "Ihorombe": [
            "Ihosy", "Ivohibe", "Iakora",
        ],
        "Amoron'i Mania": [
            "Ambositra", "Fandriana", "Ambatofinandrahana",
            "Manandriana",
        ],
        "Haute Matsiatra": [
            "Fianarantsoa", "Ambalavao", "Ambohimahasoa",
            "Ikalamavony", "Lalangina",
        ],
        "Itasy": [
            "Miarinarivo", "Arivonimamo", "Soavinandriana",
        ],
    },
    "mozambique": {
        "Maputo Province": [
            "Matola", "Boane", "Marracuene",
            "Namaacha", "Moamba",
        ],
        "Gaza": [
            "Xai-Xai", "Chokwe", "Chibuto",
            "Bilene", "Guijá", "Massingir",
        ],
        "Inhambane": [
            "Inhambane", "Maxixe", "Vilankulo",
            "Morrumbene", "Zavala", "Massinga",
        ],
        "Sofala": [
            "Beira", "Dondo", "Buzi",
            "Chibabava", "Gorongosa", "Nhamatanda",
        ],
        "Manica": [
            "Chimoio", "Gondola", "Manica",
            "Sussundenga", "Barué",
        ],
        "Zambezia": [
            "Quelimane", "Mocuba", "Maganja da Costa",
            "Alto Molócue", "Guruè", "Milange",
        ],
        "Tete": [
            "Tete", "Moatize", "Cahora Bassa",
            "Angónia", "Changara",
        ],
        "Nampula": [
            "Nampula", "Nacala", "Angoche",
            "Monapo", "Ilha de Moçambique",
        ],
        "Cabo Delgado": [
            "Pemba", "Mocimboa da Praia", "Mueda",
            "Montepuez", "Palma", "Macomia",
        ],
        "Niassa": [
            "Lichinga", "Cuamba", "Mandimba",
            "Marrupa", "Mecula",
        ],
    },
}


def get_gazetteer_hierarchy(
    country: str,
) -> dict[str, list[str]] | None:
    """Return admin hierarchy for a country from built-in gazetteer."""
    return COUNTRY_GAZETTEERS.get(country.strip().lower())


def build_auto_admin_hierarchy(
    countries: list[str],
) -> dict[str, list[str]]:
    """Build a merged admin hierarchy for given countries."""
    merged: dict[str, list[str]] = {}
    for c in countries:
        gaz = get_gazetteer_hierarchy(c)
        if gaz:
            for admin1, districts in gaz.items():
                merged[admin1] = districts
    return merged


# ── Number extraction patterns ────────────────────────────────────────
# Pattern 1: NUM + keyword (e.g. "48,000 displaced")
_NUMBER_PATTERN = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*"
    r"(people|persons|individuals|deaths|dead|killed|"
    r"displaced|injured|missing|houses|homes|affected|"
    r"families|households|children|schools|"
    r"health\s*facilit)",
    re.IGNORECASE,
)

# Pattern 2: "death toll ... NUM" / "rises to NUM" / "at least NUM"
# Pattern 2: "death toll rises to NUM" / "kills NUM" / "toll hits NUM"
# Connecting verbs only — prevents runaway matching across unrelated clauses.
_TOLL_PATTERN = re.compile(
    r"(?:death\s+toll|toll)"
    r"\s+(?:rises?\s+to|hits?|reaches?|climbs?\s+to|stands?\s+at|now)\s+"
    r"(\d[\d,]*)"
    r"|"
    r"(?:kills?|killed)\s+(\d[\d,]*)",
    re.IGNORECASE,
)

# Pattern 3: "at least/over/more than NUM keyword"
_ATLEAST_PATTERN = re.compile(
    r"(?:at\s+least|over|more\s+than|nearly|approximately|"
    r"about|up\s+to|around|some)\s+"
    r"(\d[\d,]*(?:\.\d+)?)\s*"
    r"(people|persons|dead|killed|deaths|displaced|injured|"
    r"missing|affected|houses|homes|children|families|"
    r"schools|health)",
    re.IGNORECASE,
)

# Pattern 4: "NUM killed/dead/deaths" at sentence level
_SENTENCE_FIGURE_PATTERN = re.compile(
    r"\b(\d[\d,]*)\b[^.]{0,30}\b"
    r"(killed|dead|deaths|drowned|perished|fatalities)",
    re.IGNORECASE,
)


def _extract_figures(text: str) -> dict[str, int]:
    """Extract numeric figures from text using multiple patterns."""
    figures: dict[str, int] = {}

    def _accum(key: str, value: int) -> None:
        figures[key] = max(figures.get(key, 0), value)

    # Pattern 1: standard NUM + keyword
    for match in _NUMBER_PATTERN.finditer(text):
        raw_num = match.group(1).replace(",", "")
        try:
            value = int(float(raw_num))
        except ValueError:
            continue
        label = match.group(2).strip().lower()
        if label in ("deaths", "dead", "killed"):
            _accum("deaths", value)
        elif label == "displaced":
            _accum("displaced", value)
        elif label == "injured":
            _accum("injured", value)
        elif label == "missing":
            _accum("missing", value)
        elif label in ("houses", "homes"):
            _accum("houses_affected", value)
        elif label in (
            "people", "persons", "individuals",
            "affected", "families", "households",
        ):
            _accum("people_affected", value)
        elif label == "children":
            _accum("children_affected", value)
        elif label == "schools":
            _accum("schools_affected", value)
        elif label.startswith("health"):
            _accum("health_facilities_affected", value)

    # Pattern 2: "death toll rises to 59" / "kills 4"
    for match in _TOLL_PATTERN.finditer(text):
        raw_num = (match.group(1) or match.group(2) or "").replace(",", "")
        try:
            value = int(float(raw_num))
        except ValueError:
            continue
        if value > 0:
            _accum("deaths", value)

    # Pattern 3: "at least 48,000 displaced"
    for match in _ATLEAST_PATTERN.finditer(text):
        raw_num = match.group(1).replace(",", "")
        try:
            value = int(float(raw_num))
        except ValueError:
            continue
        label = match.group(2).strip().lower()
        if label in ("dead", "killed", "deaths"):
            _accum("deaths", value)
        elif label == "displaced":
            _accum("displaced", value)
        elif label == "injured":
            _accum("injured", value)
        elif label == "missing":
            _accum("missing", value)
        elif label in ("houses", "homes"):
            _accum("houses_affected", value)
        elif label in (
            "people", "persons", "affected",
            "families",
        ):
            _accum("people_affected", value)
        elif label == "children":
            _accum("children_affected", value)
        elif label == "schools":
            _accum("schools_affected", value)
        elif label.startswith("health"):
            _accum("health_facilities_affected", value)

    # Pattern 4: "59 killed" / "40 dead" in sentence context
    for match in _SENTENCE_FIGURE_PATTERN.finditer(text):
        raw_num = match.group(1).replace(",", "")
        try:
            value = int(float(raw_num))
        except ValueError:
            continue
        if 0 < value < 1_000_000:
            _accum("deaths", value)

    return figures


def _classify_impact_type(text: str) -> ImpactType:
    """Classify the dominant impact type from text."""
    haystack = text.lower()
    scores: dict[ImpactType, int] = {}
    for itype, keywords in _IMPACT_KEYWORDS.items():
        scores[itype] = sum(
            1 for kw in keywords if kw in haystack
        )
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else ImpactType.PEOPLE


def _classify_all_impact_types(text: str) -> list[ImpactType]:
    """Return **all** impact types with keyword matches, ordered by score.

    A single Flash Update may mention deaths (PEOPLE), destroyed bridges
    (INFRASTRUCTURE), and damaged clinics (SERVICES).  This function
    returns all matching types so the caller can create one
    ``ImpactObservation`` per type.  Falls back to ``[ImpactType.PEOPLE]``
    if nothing matches.
    """
    haystack = text.lower()
    scored: list[tuple[ImpactType, int]] = []
    for itype, keywords in _IMPACT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in haystack)
        if score > 0:
            scored.append((itype, score))
    if not scored:
        return [ImpactType.PEOPLE]
    scored.sort(key=lambda t: t[1], reverse=True)
    return [itype for itype, _ in scored]


def _classify_need_types(text: str) -> list[NeedType]:
    """Find all need types mentioned in text."""
    haystack = text.lower()
    found: list[NeedType] = []
    for ntype, keywords in _NEED_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            found.append(ntype)
    return found


def _severity_from_text(text: str) -> int:
    """Estimate IPC-like severity phase from text keywords."""
    h = text.lower()
    if any(
        k in h
        for k in [
            "catastroph", "famine", "system collapse",
            "mass casualty",
        ]
    ):
        return 5
    if any(
        k in h
        for k in [
            "state of emergency", "emergency declaration",
            "severe", "widespread destruction",
        ]
    ):
        return 4
    if any(
        k in h
        for k in [
            "significant", "critical", "major",
            "crisis", "large-scale",
        ]
    ):
        return 3
    if any(
        k in h for k in ["elevated", "moderate", "stressed", "warning"]
    ):
        return 2
    return 1


def _is_risk_text(text: str) -> bool:
    h = text.lower()
    return any(kw in h for kw in _RISK_KEYWORDS)


def _detect_response_actor(
    text: str,
) -> tuple[str, str] | None:
    h = text.lower()
    for keyword, actor_type in _RESPONSE_ACTOR_KEYWORDS.items():
        if keyword in h:
            return keyword.upper(), actor_type
    return None


def build_ontology_from_evidence(
    evidence: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,  # noqa: ARG001
    admin_hierarchy: dict[str, list[str]] | None = None,
) -> HumanitarianOntologyGraph:
    """Build an ontology graph from crawler evidence dicts.

    Parameters
    ----------
    evidence:
        List of evidence dicts (from ``build_graph_context``).
    meta:
        Optional metadata dict from graph context.
    admin_hierarchy:
        Optional mapping of admin1 → [admin2 names].
        If provided, populates geographic hierarchy.
        If not provided, uses built-in country gazetteers.
    """
    graph = HumanitarianOntologyGraph()

    # Auto-detect countries from evidence for gazetteer lookup
    if not admin_hierarchy:
        seen_countries: set[str] = set()
        for ev in evidence:
            c = str(ev.get("country", "")).strip()
            if c:
                seen_countries.add(c)
        # Use dynamic gazetteer system (loads from file / generates via LLM)
        try:
            from .gazetteers import build_admin_hierarchy
            admin_hierarchy = build_admin_hierarchy(
                list(seen_countries)
            )
        except Exception:
            admin_hierarchy = build_auto_admin_hierarchy(
                list(seen_countries)
            )

    # Pre-populate admin hierarchy
    if admin_hierarchy:
        for admin1, districts in admin_hierarchy.items():
            graph.add_geo(admin1, admin_level=1)
            for d in districts:
                graph.add_geo(d, admin_level=2, parent=admin1)

    for ev in evidence:
        country = str(ev.get("country", "")).strip()
        country_iso3 = str(ev.get("country_iso3", "")).strip()
        disaster_type = str(
            ev.get("disaster_type", "")
        ).strip().lower()
        title = str(ev.get("title", ""))
        summary = str(ev.get("summary", ""))
        text = str(ev.get("text", ""))
        url = str(ev.get("url", ""))
        connector = str(ev.get("connector", ""))
        severity = str(ev.get("severity", "medium"))
        confidence = str(ev.get("confidence", "medium"))
        published_at = ev.get("published_at")
        source_label = str(ev.get("source_label", "unknown"))
        combined = " ".join([title, summary, text])

        # Source credibility tier (injected by annotate_evidence or computed here)
        cred_tier = ev.get("credibility_tier")
        if cred_tier is None:
            try:
                from .source_credibility import source_tier as _src_tier
                cred_tier = _src_tier(
                    connector=connector,
                    source_type=str(ev.get("source_type", "")),
                )
            except Exception:
                cred_tier = 4

        # Geo — resolve ISO3 if not provided
        if country:
            _iso3 = country_iso3
            if not _iso3:
                try:
                    from .gazetteers import country_to_iso3 as _c2i
                    _iso3 = _c2i(country) or ""
                except Exception:
                    _iso3 = ""
            graph.add_geo(country, admin_level=0, iso3=_iso3)

        # Hazard
        if disaster_type:
            cat = HAZARD_CATEGORY_MAP.get(
                disaster_type, HazardCategory.METEOROLOGICAL
            )
            sub_hazards = _detect_sub_hazards(combined)
            graph.add_hazard(
                name=disaster_type,
                category=cat,
                specific_type=disaster_type,
                sub_hazards=sub_hazards,
            )

        # Claim
        graph.add_claim(SourceClaim(
            claim_text=summary[:500],
            source_url=url,
            source_label=source_label,
            connector=connector,
            published_at=str(published_at) if published_at else None,
            confidence=confidence,
            credibility_tier=cred_tier,
        ))

        # Figures extraction (Rust-accelerated when available)
        figures = _rust_extract_figures(combined) if _USE_RUST_FIGURES else _extract_figures(combined)
        sev_phase = _map_severity_to_phase(severity)

        # Multi-impact: one ImpactObservation per detected impact type.
        # Rust path: single dominant type (Rust classifier is single-label).
        # Python path: all matching types via _classify_all_impact_types.
        if _USE_RUST:
            _rust_it = _rust_classify_impact_type(combined)
            try:
                all_impact_types = [ImpactType(_rust_it)]
            except ValueError:
                all_impact_types = [ImpactType.PEOPLE]
        else:
            all_impact_types = _classify_all_impact_types(combined)

        # Determine geographic target
        geo_target = country
        admin_level = 0
        detected_geo = _detect_admin_area(
            combined, graph.geo_areas
        )
        if detected_geo:
            geo_target = detected_geo.name
            admin_level = detected_geo.admin_level

        # Normalize date to YYYY-MM-DD for temporal layer
        _reported_date = str(published_at)[:10] if published_at else ""

        # Create one ImpactObservation per impact type found in this evidence.
        # The primary (highest-scoring) type gets the full figures dict;
        # secondary types get an empty figures dict to avoid double-counting.
        for idx, impact_type in enumerate(all_impact_types):
            graph.add_impact(ImpactObservation(
                description=summary[:300],
                impact_type=impact_type,
                geo_area=geo_target,
                admin_level=admin_level,
                severity_phase=sev_phase,
                figures=figures if idx == 0 else {},
                source_url=url,
                source_connector=connector,
                confidence=confidence,
                reported_date=_reported_date,
                source_label=source_label,
                credibility_tier=cred_tier,
            ))

        # Need extraction (Rust-accelerated when available)
        if _USE_RUST:
            _rust_nts = _rust_classify_need_types(combined)
            need_types: list[NeedType] = []
            for _rn in _rust_nts:
                try:
                    need_types.append(NeedType(_rn))
                except ValueError:
                    pass
        else:
            need_types = _classify_need_types(combined)
        for nt in need_types:
            graph.add_need(NeedStatement(
                description=summary[:200],
                need_type=nt,
                geo_area=geo_target,
                admin_level=admin_level,
                severity_phase=sev_phase,
                indicates_impact=all_impact_types[0].value,
                source_url=url,
                reported_date=_reported_date,
                source_label=source_label,
            ))

        # Risk extraction (Rust-accelerated when available)
        _risk = _rust_is_risk_text(combined) if _USE_RUST else _is_risk_text(combined)
        if _risk:
            horizon = "48h"
            if any(
                k in combined.lower()
                for k in ["7 day", "7-day", "week", "weekly"]
            ):
                horizon = "7d"
            graph.add_risk(RiskStatement(
                description=summary[:200],
                hazard_name=disaster_type,
                geo_area=geo_target,
                horizon=horizon,
                source_url=url,
                reported_date=_reported_date,
                source_label=source_label,
            ))

        # Response detection (Rust-accelerated when available)
        actor_info = _rust_detect_response_actor(combined) if _USE_RUST else _detect_response_actor(combined)
        if actor_info:
            actor_name, actor_type = actor_info
            sector = ""
            for nt in need_types[:1]:
                sector = nt.value
            graph.add_response(ResponseActivity(
                description=summary[:200],
                actor=actor_name,
                actor_type=actor_type,
                geo_area=geo_target,
                sector=sector,
                source_url=url,
            ))

    return graph


def _detect_sub_hazards(text: str) -> list[str]:
    """Detect specific sub-hazard phenomena."""
    h = text.lower()
    found: list[str] = []
    for sub in [
        "high winds", "heavy rainfall", "storm surge",
        "riverine flooding", "flash flood", "coastal flood",
        "landslide", "mudslide", "hail",
    ]:
        if sub in h:
            found.append(sub)
    return found


def _map_severity_to_phase(severity: str) -> int:
    return {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }.get(severity.strip().lower(), 2)


def _detect_admin_area(
    text: str,
    geo_areas: dict[str, GeoArea],
) -> GeoArea | None:
    """Try to match a known admin area name in text."""
    h = text.lower()
    # Prefer more specific (higher admin level) matches
    candidates = sorted(
        geo_areas.values(),
        key=lambda g: g.admin_level,
        reverse=True,
    )
    for geo in candidates:
        if geo.admin_level < 1:
            continue
        # Word-boundary match to avoid false positives
        pattern = (
            r"(?<!\w)"
            + re.escape(geo.name.lower())
            + r"(?!\w)"
        )
        if re.search(pattern, h):
            return geo
    return None

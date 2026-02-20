"""OCHA-style Situation Analysis renderer.

Produces a detailed multi-section markdown report following the OCHA
Situation Analysis structure (not SitRep), including:

 1. Executive Summary (event card + key figures)
 2. National Impact Overview (table + narrative)
 3. Admin 1 Impact Summary (province table)
 4. Admin 2 District-Level Detail (per-province tables)
 5-10. Sectoral Analyses (Shelter, WASH, Health, Food Security, Protection, Education)
 11. Access Constraints
 12. Outstanding Needs & Gaps
 13. Forecast & Risk Outlook
 14. Annex — Admin Reference
 15. Citations

Uses the ``graph_ontology`` module for structured evidence traversal
and the ``reporting`` module for evidence gathering and citation logic.
"""

from __future__ import annotations

import json
import logging
import re as _re_module
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

from .graph_ontology import (
    HumanitarianOntologyGraph,
    NeedStatement,
    NeedType,
    build_ontology_from_evidence,
)
from .reporting import (
    build_graph_context,
    write_report_file,
)
from .llm_utils import (
    build_citation_numbers as _build_citation_numbers,
    extract_json_object as _extract_json_object,
    extract_responses_text as _extract_responses_text,
)
from .sa_quality_gate import quality_summary_markdown, score_situation_analysis
from .settings import get_openai_api_key, get_openai_model


# ── Template loader ──────────────────────────────────────────────────

_DEFAULT_SA_TEMPLATE = Path("config") / "report_template.situation_analysis.json"


def load_sa_template(path: Path | None = None) -> dict[str, Any]:
    """Load Situation Analysis template from JSON config."""
    candidate = path or (Path.cwd() / _DEFAULT_SA_TEMPLATE)
    if candidate.exists():
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Minimal fallback
    return {
        "name": "situation-analysis-fallback",
        "sections": {
            "executive_summary": "Executive Summary",
            "national_impact": "National Impact Overview",
            "admin1_summary": "Province-Level (Admin 1) Impact Summary",
            "admin2_detail": "District-Level (Admin 2) Detailed Impact Tables",
            "sectoral_shelter": "Shelter & Housing",
            "sectoral_wash": "Water, Sanitation & Hygiene (WASH)",
            "sectoral_health": "Health",
            "sectoral_food_security": "Food Security, Nutrition & Livelihoods",
            "sectoral_protection": "Protection",
            "sectoral_education": "Education",
            "access_constraints": "Access Constraints",
            "outstanding_needs": "Outstanding Needs & Gaps",
            "forecast_risk": "Forecast & Risk Outlook",
            "annex": "Annex — Full Admin 1 & Admin 2 Reference List",
            "citations": "Sources and References",
        },
        "limits": {},
    }


# ── Sector ↔ NeedType mapping ────────────────────────────────────────

_SECTOR_NEED_MAP: dict[str, NeedType] = {
    "shelter": NeedType.SHELTER,
    "wash": NeedType.WASH,
    "health": NeedType.HEALTH,
    "food_security": NeedType.FOOD_SECURITY,
    "protection": NeedType.PROTECTION,
    "education": NeedType.EDUCATION,
}

_SECTOR_KEYS = [
    "sectoral_shelter",
    "sectoral_wash",
    "sectoral_health",
    "sectoral_food_security",
    "sectoral_protection",
    "sectoral_education",
]


# ── Auto-inference helpers ───────────────────────────────────────────

import re as _re

# Named-storm pattern: "Cyclone Xyz", "Typhoon Abc", "Hurricane Def"
# The category keyword is case-insensitive but the proper name MUST start with a capital letter.
_EVENT_NAME_RE = _re.compile(
    r"\b((?:[Tt]ropical\s+)?(?:[Cc]yclone|[Tt]yphoon|[Hh]urricane|[Ss]torm|[Ee]arthquake|[Ff]lood|[Dd]rought))"
    r"\s+([A-Z][a-zà-ÿ]+)",
)

# Extended event name patterns for non-storm crises
_CRISIS_NAME_PATTERNS: list[tuple[_re.Pattern[str], str]] = [
    # "Ethiopia Conflict", "Sudan Crisis", "South Sudan Civil War"
    (_re.compile(r"\b([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)?)\s+(Crisis|Conflict|Emergency|War|Civil War)\b"), "{0} {1}"),
    # "Cholera Outbreak in Ethiopia", "Mpox Epidemic"
    (_re.compile(r"\b(Cholera|Ebola|Measles|Mpox|Dengue|Meningitis|Polio|Yellow Fever|Plague|Avian Flu)\s+(Outbreak|Epidemic|Emergency)\b", _re.IGNORECASE), "{0} {1}"),
    # "Horn of Africa Drought", "East Africa Food Crisis"
    (_re.compile(r"\b([\w\s]+?)\s+(Drought|Famine|Food Crisis|Food Security Crisis|Hunger Crisis)\b"), "{0} {1}"),
]

# Disaster-type keywords (mapped to canonical OCHA types)
_DISASTER_TYPE_KEYWORDS: dict[str, str] = {
    "cyclone": "Tropical Cyclone",
    "typhoon": "Tropical Cyclone",
    "hurricane": "Tropical Cyclone",
    "tropical storm": "Tropical Storm",
    "flood": "Flood",
    "flooding": "Flood",
    "earthquake": "Earthquake",
    "drought": "Drought",
    "landslide": "Landslide",
    "tsunami": "Tsunami",
    "volcanic": "Volcanic Eruption",
    "conflict": "Conflict",
    "conflict emergency": "Conflict",
    "epidemic": "Epidemic",
    "epidemic/disease outbreak": "Epidemic",
    "disease outbreak": "Epidemic",
    "cholera": "Epidemic",
    "famine": "Famine",
    "food insecurity": "Food Security Crisis",
    "food crisis": "Food Security Crisis",
}

# Map from canonical event type → fallback name template when no specific name found
_EVENT_TYPE_FALLBACK: dict[str, str] = {
    "Tropical Cyclone": "{country} Tropical Cyclone",
    "Tropical Storm": "{country} Tropical Storm",
    "Flood": "{country} Floods",
    "Earthquake": "{country} Earthquake",
    "Drought": "{country} Drought",
    "Landslide": "{country} Landslide",
    "Tsunami": "{country} Tsunami",
    "Volcanic Eruption": "{country} Volcanic Eruption",
    "Conflict": "{country} Conflict",
    "Epidemic": "{country} Disease Outbreak",
    "Famine": "{country} Food Crisis",
    "Food Security Crisis": "{country} Food Security Crisis",
}


def _infer_event_name(
    evidence: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
) -> str:
    """Scan evidence titles/text for a named event.

    Resolution order:
      1. Named storm regex (e.g. "Cyclone Gezani")
      2. Extended crisis patterns (e.g. "Ethiopia Conflict", "Cholera Outbreak")
      3. Fallback from event type + country (e.g. "Ethiopia Disease Outbreak")
    """
    # Pass 1: Named storm pattern (most specific)
    name_counts: Counter[str] = Counter()
    for item in evidence:
        for field in ("title", "text", "summary"):
            text = item.get(field, "") or ""
            for m in _EVENT_NAME_RE.finditer(text):
                category = m.group(1).strip().title()
                name = m.group(2).strip().title()
                name_counts[f"{category} {name}"] += 1
    if name_counts:
        return name_counts.most_common(1)[0][0]

    # Pass 2: Extended crisis name patterns
    crisis_counts: Counter[str] = Counter()
    for item in evidence:
        for field in ("title", "text", "summary"):
            text = item.get(field, "") or ""
            for pattern, fmt in _CRISIS_NAME_PATTERNS:
                for m in pattern.finditer(text):
                    name = fmt.format(m.group(1).strip().title(), m.group(2).strip().title())
                    crisis_counts[name] += 1
    if crisis_counts:
        return crisis_counts.most_common(1)[0][0]

    # Pass 3: Construct from event type + country
    country = ""
    if meta:
        countries = meta.get("countries") or []
        if isinstance(countries, list) and countries:
            country = countries[0].strip().title()
        elif isinstance(countries, str) and countries:
            country = countries.strip().title()
    if not country:
        # Try extracting from evidence
        for item in evidence:
            c = str(item.get("country", "")).strip()
            if c:
                country = c.title()
                break

    event_type = _infer_event_type(evidence, meta or {})
    if country and event_type:
        template = _EVENT_TYPE_FALLBACK.get(event_type, "{country} Humanitarian Situation")
        return template.format(country=country)
    if country:
        return f"{country} Humanitarian Situation"
    return ""


def _infer_event_type(
    evidence: list[dict[str, Any]], meta: dict[str, Any]
) -> str:
    """Infer disaster type from evidence or meta."""
    # Check meta first (countries / disaster_types from CLI)
    dt = meta.get("disaster_types") or []
    if dt:
        raw = dt[0] if isinstance(dt, list) else str(dt)
        return _DISASTER_TYPE_KEYWORDS.get(raw.lower(), raw.title())

    # Scan evidence text
    type_counts: Counter[str] = Counter()
    for item in evidence:
        blob = " ".join(
            str(item.get(f, "")) for f in ("title", "text", "summary")
        ).lower()
        for kw, canon in _DISASTER_TYPE_KEYWORDS.items():
            if kw in blob:
                type_counts[canon] += 1
    if type_counts:
        return type_counts.most_common(1)[0][0]
    return ""


# ── Access-constraint extraction ─────────────────────────────────────

_ACCESS_KEYWORDS = _re.compile(
    r"(road[s]?\s+(?:cut|block|impassable|damaged|destroy))|"
    r"(bridge[s]?\s+(?:collapse|destroy|wash|damage))|"
    r"(access\s+(?:restrict|limit|constrain|cut|block|hamper|difficult))|"
    r"(strand|isolat|maroon|cut.off|unreachable)|"
    r"(communication[s]?\s+(?:down|disrupt|cut|lost))",
    _re.IGNORECASE,
)


def _extract_access_constraints(evidence: list[dict[str, Any]]) -> list[str]:
    """Return unique access-constraint snippets from evidence."""
    constraints: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        blob = " ".join(
            str(item.get(f, "")) for f in ("title", "text", "summary")
        )
        for m in _ACCESS_KEYWORDS.finditer(blob):
            # Grab surrounding context (sentence-ish)
            start = max(0, m.start() - 40)
            end = min(len(blob), m.end() + 80)
            snippet = blob[start:end].strip()
            if snippet and snippet not in seen:
                seen.add(snippet)
                constraints.append(snippet)
    return constraints


# ── Citation span locking ────────────────────────────────────────────

_CITATION_REF_RE = _re_module.compile(r"\[(\d+)\]")


def validate_sa_citations(
    narrative: dict[str, str],
    citation_numbers: dict[str, int],
) -> dict[str, Any]:
    """Validate citation references in SA LLM narratives.

    Checks that every ``[N]`` reference in each narrative section maps
    to an actual citation number in the citation index.

    Returns a quality dict with per-section and overall stats.
    """
    valid_numbers = set(citation_numbers.values())
    total_refs = 0
    valid_refs = 0
    invalid_refs = 0
    sections_with_refs = 0
    section_details: dict[str, dict[str, Any]] = {}

    for key, text in narrative.items():
        if not isinstance(text, str):
            continue
        refs = _CITATION_REF_RE.findall(text)
        section_total = len(refs)
        section_valid = sum(1 for r in refs if int(r) in valid_numbers)
        section_invalid = section_total - section_valid
        total_refs += section_total
        valid_refs += section_valid
        invalid_refs += section_invalid
        if section_total > 0:
            sections_with_refs += 1
        section_details[key] = {
            "total_refs": section_total,
            "valid_refs": section_valid,
            "invalid_refs": section_invalid,
        }

    total_sections = len(narrative)
    citation_coverage = sections_with_refs / total_sections if total_sections else 0.0
    accuracy = valid_refs / total_refs if total_refs else 1.0

    return {
        "total_refs": total_refs,
        "valid_refs": valid_refs,
        "invalid_refs": invalid_refs,
        "sections_with_refs": sections_with_refs,
        "total_sections": total_sections,
        "citation_coverage": round(citation_coverage, 3),
        "citation_accuracy": round(accuracy, 3),
        "section_details": section_details,
    }


def strip_invalid_citations(
    narrative: dict[str, str],
    citation_numbers: dict[str, int],
) -> dict[str, str]:
    """Remove invalid ``[N]`` references from narrative text.

    Any ``[N]`` where N is not in the citation index is stripped
    to prevent misleading references.
    """
    valid_numbers = set(citation_numbers.values())
    cleaned: dict[str, str] = {}
    for key, text in narrative.items():
        if not isinstance(text, str):
            cleaned[key] = text
            continue

        def _replace(m: _re_module.Match) -> str:
            n = int(m.group(1))
            return m.group(0) if n in valid_numbers else ""

        cleaned[key] = _CITATION_REF_RE.sub(_replace, text).strip()
    return cleaned


# ── Main renderer ────────────────────────────────────────────────────

def render_situation_analysis(
    *,
    graph_context: dict[str, Any],
    title: str = "Situation Analysis",
    event_name: str = "",
    event_type: str = "",
    period: str = "",
    admin_hierarchy: dict[str, list[str]] | None = None,
    template_path: Path | None = None,
    use_llm: bool = False,
    quality_gate: bool = False,
    quality_thresholds: dict[str, float] | None = None,
) -> str:
    """Render a full OCHA Situation Analysis from graph evidence.

    Parameters
    ----------
    graph_context:
        Output from ``build_graph_context()``.
    title:
        Report title.
    event_name:
        E.g. "Tropical Cyclone Gezani-26".
    event_type:
        E.g. "Cyclone/storm".
    period:
        E.g. "2-6 March 2026".
    admin_hierarchy:
        Dict mapping admin1 names → list of admin2 district names.
    template_path:
        Path to SA template JSON.
    use_llm:
        If True, use LLM for narrative sections.
    """
    evidence = graph_context.get("evidence", [])
    meta = graph_context.get("meta", {})
    template = load_sa_template(template_path)
    sections = template.get("sections", {})
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # Auto-infer event name and type from evidence if not provided
    if not event_name:
        event_name = _infer_event_name(evidence, meta)
    if not event_type:
        event_type = _infer_event_type(evidence, meta)

    # Build ontology graph
    ontology = build_ontology_from_evidence(
        evidence=evidence,
        meta=meta,
        admin_hierarchy=admin_hierarchy,
    )

    # Citation index
    citation_numbers = _build_citation_numbers(evidence)

    # National figures
    nat_figures = ontology.national_figures()
    nat_figures_dated = ontology.national_figures_with_dates()
    max_severity = ontology.max_national_severity()

    # Admin aggregations
    admin1_agg = ontology.aggregate_figures_by_admin1()
    sector_summary = ontology.sector_summary()

    # LLM sections (optional)
    llm_narrative: dict[str, str] = {}
    if use_llm:
        llm_narrative = _generate_llm_narratives(
            graph_context=graph_context,
            ontology=ontology,
            template=template,
            citation_numbers=citation_numbers,
            event_name=event_name,
        )
        # Citation span locking — strip any invalid [N] refs
        if llm_narrative:
            llm_narrative = strip_invalid_citations(llm_narrative, citation_numbers)

    lines: list[str] = []

    # ── HEADER ──────────────────────────────────────────────
    lines.append(f"# {title}")
    lines.append("")
    if use_llm:
        lines.append("AI Assisted: Yes")
        lines.append("")
    lines.append(f"Generated: {generated_at}")
    lines.append("")

    # ── 1. EXECUTIVE SUMMARY ────────────────────────────────
    lines.append(f"## {sections.get('executive_summary', 'Executive Summary')}")
    lines.append("")
    _render_event_card(
        lines, event_name=event_name, event_type=event_type, period=period,
        ontology=ontology, meta=meta,
    )
    _render_key_figures(lines, nat_figures=nat_figures, max_severity=max_severity)
    lines.append("")

    if llm_narrative.get("executive_summary"):
        lines.append(llm_narrative["executive_summary"])
    else:
        _render_exec_summary_deterministic(
            lines, meta=meta, ontology=ontology, nat_figures=nat_figures,
            admin1_agg=admin1_agg, event_name=event_name, event_type=event_type,
        )
    lines.append("")

    # ── 2. NATIONAL IMPACT OVERVIEW ─────────────────────────
    lines.append(f"## {sections.get('national_impact', 'National Impact Overview')}")
    lines.append("")
    _render_national_impact_table(lines, nat_figures=nat_figures, nat_figures_dated=nat_figures_dated, template=template)
    lines.append("")
    if llm_narrative.get("national_impact"):
        lines.append(llm_narrative["national_impact"])
    else:
        _render_national_narrative(lines, nat_figures=nat_figures, nat_figures_dated=nat_figures_dated, ontology=ontology)
    lines.append("")

    # ── 3. ADMIN 1 (PROVINCE) SUMMARY ──────────────────────
    lines.append(f"## {sections.get('admin1_summary', 'Province-Level (Admin 1) Impact Summary')}")
    lines.append("")
    _render_admin1_table(lines, admin1_agg=admin1_agg, template=template)
    lines.append("")

    # ── 4. ADMIN 2 (DISTRICT) DETAIL ───────────────────────
    lines.append(f"## {sections.get('admin2_detail', 'District-Level (Admin 2) Detailed Impact Tables')}")
    lines.append("")
    _render_admin2_tables(
        lines, ontology=ontology, admin1_agg=admin1_agg,
        template=template, llm_narrative=llm_narrative,
    )

    # ── 5-10. SECTORAL ANALYSES ─────────────────────────────
    for sector_key in _SECTOR_KEYS:
        section_label = sections.get(sector_key, sector_key.replace("sectoral_", "").replace("_", " ").title())
        lines.append(f"## {section_label}")
        lines.append("")
        clean_key = sector_key.replace("sectoral_", "")
        _render_sector_section(
            lines,
            sector_key=clean_key,
            ontology=ontology,
            template=template,
            llm_narrative=llm_narrative,
        )
        lines.append("")

    # ── 11. ACCESS CONSTRAINTS ──────────────────────────────
    lines.append(f"## {sections.get('access_constraints', 'Access Constraints')}")
    lines.append("")
    if llm_narrative.get("access_constraints"):
        lines.append(llm_narrative["access_constraints"])
    else:
        # Try to extract access-related data from evidence
        access_snippets = _extract_access_constraints(evidence)
        if access_snippets:
            lines.append("| # | Constraint | Source Context |")
            lines.append("|---|-----------|----------------|")
            for idx, snippet in enumerate(access_snippets[:10], 1):
                lines.append(f"| {idx} | {snippet} | Evidence |")
        else:
            lines.append("| District | Status | Roads Affected | Bridge Damage | Notes |")
            lines.append("|----------|--------|----------------|---------------|-------|")
            lines.append("| _No access constraint data extracted from current evidence_ | — | — | — | — |")
    lines.append("")

    # ── 12. OUTSTANDING NEEDS & GAPS ────────────────────────
    lines.append(f"## {sections.get('outstanding_needs', 'Outstanding Needs & Gaps')}")
    lines.append("")
    _render_outstanding_needs(lines, sector_summary=sector_summary, template=template, llm_narrative=llm_narrative)
    lines.append("")

    # ── 13. FORECAST & RISK OUTLOOK ─────────────────────────
    lines.append(f"## {sections.get('forecast_risk', 'Forecast & Risk Outlook')}")
    lines.append("")
    _render_forecast(lines, ontology=ontology, template=template, llm_narrative=llm_narrative)
    lines.append("")

    # ── 14. ANNEX ───────────────────────────────────────────
    lines.append(f"## {sections.get('annex', 'Annex — Full Admin 1 & Admin 2 Reference List')}")
    lines.append("")
    _render_annex(lines, ontology=ontology)
    lines.append("")

    # ── 15. CITATIONS ───────────────────────────────────────
    lines.append(f"## {sections.get('citations', 'Sources and References')}")
    lines.append("")
    for url, n in sorted(citation_numbers.items(), key=lambda x: x[1]):
        lines.append(f"{n}. {url}")
    lines.append("")

    report_md = "\n".join(lines) + "\n"

    # ── QUALITY GATE ────────────────────────────────────────
    if quality_gate:
        qa_result = score_situation_analysis(
            report_md,
            citation_numbers=citation_numbers,
            thresholds=quality_thresholds,
        )
        report_md = report_md.rstrip("\n") + quality_summary_markdown(qa_result) + "\n"
        _log.info(
            "SA quality gate: score=%.3f passed=%s",
            qa_result.overall_score,
            qa_result.passed,
        )

    return report_md


# ── Section renderers ────────────────────────────────────────────────

def _render_event_card(
    lines: list[str],
    *,
    event_name: str,
    event_type: str,
    period: str,
    ontology: HumanitarianOntologyGraph,
    meta: dict[str, Any],
) -> None:
    """Render the event identification card."""
    lines.append("### Event Card")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| **Event** | {event_name or 'Unknown Event'} |")
    lines.append(f"| **Type** | {event_type or 'Not specified'} |")

    # Hazards
    hazards = ", ".join(
        h.name for h in ontology.hazards.values()
    ) or "—"
    lines.append(f"| **Hazards** | {hazards} |")

    lines.append(f"| **Period** | {period or 'Ongoing'} |")

    # Worst affected provinces
    admin1 = ontology.admin1_areas()
    if admin1:
        worst_adm1 = ", ".join(a.name for a in admin1[:5])
        lines.append(f"| **Worst Affected Provinces** | {worst_adm1} |")

    # Countries from evidence
    countries = sorted(meta.get("by_country", {}).keys())
    if countries:
        lines.append(f"| **Countries** | {', '.join(countries)} |")

    lines.append("")


def _render_key_figures(
    lines: list[str],
    *,
    nat_figures: dict[str, int],
    max_severity: int,
) -> None:
    """Render Key Figures side-panel style."""
    lines.append("### Key Figures")
    lines.append("")
    figure_labels = [
        ("deaths", "Deaths"),
        ("missing", "Missing"),
        ("injured", "Injured"),
        ("displaced", "Displaced (in accommodation centres)"),
        ("people_affected", "Affected Population"),
        ("houses_affected", "Houses Damaged/Destroyed"),
        ("children_affected", "Children Affected"),
        ("schools_affected", "Schools Damaged"),
        ("health_facilities_affected", "Health Facilities Damaged"),
    ]
    lines.append("| Indicator | Figure |")
    lines.append("|-----------|--------|")
    for key, label in figure_labels:
        value = nat_figures.get(key, 0)
        if value > 0:
            lines.append(f"| {label} | {value:,} |")
    lines.append(f"| **Severity Phase** | **{max_severity}** |")
    lines.append("")


def _render_exec_summary_deterministic(
    lines: list[str],
    *,
    meta: dict[str, Any],
    ontology: HumanitarianOntologyGraph,
    nat_figures: dict[str, int],
    admin1_agg: dict[str, dict[str, Any]],
    event_name: str = "",
    event_type: str = "",
) -> None:
    """Deterministic executive summary from evidence facets."""
    # Lead sentence with event context
    if event_name:
        lead = f"**Event:** {event_name}"
        if event_type:
            lead += f" ({event_type})"
        lead += "."
        lines.append(lead)

    lines.append(f"**Scale:** {meta.get('events_selected', 0)} evidence items "
                 f"from {meta.get('cycles_analyzed', 0)} monitoring cycles.")

    # Geographic spread
    provinces = sorted(admin1_agg.keys())
    if provinces:
        province_names = [admin1_agg[k].get("name", k) for k in provinces]
        lines.append(f"**Geographic Spread:** {len(provinces)} provinces affected — "
                     f"{', '.join(province_names[:6])}"
                     f"{'...' if len(provinces) > 6 else ''}.")

    # Worst hit
    if admin1_agg:
        worst = max(
            admin1_agg.values(),
            key=lambda b: b.get("max_severity", 0),
        )
        lines.append(f"**Worst Affected Province:** {worst.get('name', 'Unknown')} "
                     f"(severity phase {worst.get('max_severity', 0)}, "
                     f"{worst.get('impact_count', 0)} impact observations).")

    # Displacement
    displaced = nat_figures.get("displaced", 0)
    if displaced > 0:
        lines.append(f"**Displacement:** Approximately {displaced:,} people displaced.")

    # Deaths
    deaths = nat_figures.get("deaths", 0)
    if deaths > 0:
        lines.append(f"**Fatalities:** {deaths:,} confirmed deaths reported.")

    # Response snapshot
    if ontology.responses:
        actor_types = Counter(r.actor_type for r in ontology.responses)
        lines.append(f"**Response:** {len(ontology.responses)} response activities identified "
                     f"({', '.join(f'{v} {k}' for k, v in actor_types.most_common(3))}).")

    # Risks
    if ontology.risks:
        lines.append(f"**Forward Risks:** {len(ontology.risks)} risk statements identified, "
                     f"covering {', '.join({r.hazard_name for r in ontology.risks})}.")


def _render_national_impact_table(
    lines: list[str],
    *,
    nat_figures: dict[str, int],
    nat_figures_dated: dict[str, dict[str, Any]] | None = None,
    template: dict[str, Any],
) -> None:
    """Render the national impact summary table with 'as of' dates."""
    table_def = template.get("national_impact_table", {})
    rows = table_def.get("rows", [
        "Deaths", "Missing", "Injured",
        "Displaced (in accommodation centres)",
        "Total affected population",
        "Houses fully destroyed",
        "Houses partially damaged",
        "Schools damaged",
        "Health facilities damaged",
    ])

    # Map row labels to figure keys
    _row_key_map = {
        "Deaths": "deaths",
        "Missing": "missing",
        "Injured": "injured",
        "Displaced (in accommodation centres)": "displaced",
        "Total affected population": "people_affected",
        "Houses fully destroyed": "houses_affected",
        "Houses partially damaged": "houses_affected",
        "Schools damaged": "schools_affected",
        "Health facilities damaged": "health_facilities_affected",
    }

    dated = nat_figures_dated or {}
    lines.append("| Category | Figure | As of | Source | Notes |")
    lines.append("|----------|--------|-------|--------|-------|")
    for row in rows:
        key = _row_key_map.get(row, "")
        value = nat_figures.get(key, 0)
        display = f"{value:,}" if value > 0 else "—"
        as_of = dated.get(key, {}).get("as_of", "") or "—"
        source = dated.get(key, {}).get("source", "") or "Aggregated evidence"
        lines.append(f"| {row} | {display} | {as_of} | {source} | — |")


def _render_national_narrative(
    lines: list[str],
    *,
    nat_figures: dict[str, int],
    nat_figures_dated: dict[str, dict[str, Any]] | None = None,
    ontology: HumanitarianOntologyGraph,
) -> None:
    """Short narrative for national impact with 'as of' dating."""
    dated = nat_figures_dated or {}
    total_affected = nat_figures.get("people_affected", 0)
    deaths = nat_figures.get("deaths", 0)
    displaced = nat_figures.get("displaced", 0)

    def _as_of(key: str) -> str:
        d = dated.get(key, {}).get("as_of", "")
        return f" (as of {d})" if d else ""

    parts: list[str] = []
    if total_affected:
        parts.append(f"An estimated {total_affected:,} people are affected{_as_of('people_affected')}")
    if deaths:
        parts.append(f"with {deaths:,} confirmed fatalities{_as_of('deaths')}")
    if displaced:
        parts.append(f"and approximately {displaced:,} displaced{_as_of('displaced')}")

    if parts:
        lines.append(". ".join(parts) + ".")
    else:
        lines.append("National impact figures are being compiled from available evidence.")

    # Infrastructure
    from .graph_ontology import ImpactType
    infra_impacts = ontology.impacts_by_type(ImpactType.INFRASTRUCTURE)
    if infra_impacts:
        lines.append(f"\nInfrastructure damage reported across {len(infra_impacts)} observations.")


def _render_admin1_table(
    lines: list[str],
    *,
    admin1_agg: dict[str, dict[str, Any]],
    template: dict[str, Any],
) -> None:
    """Render Admin 1 (province) summary table."""
    table_def = template.get("admin1_table", {})
    columns = table_def.get("columns", [
        "Province", "District Count", "People Affected",
        "Displaced", "Deaths", "Missing",
        "Houses Damaged", "Key Issues", "Access Constraints",
    ])
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join("---" for _ in columns) + "|"
    lines.append(header)
    lines.append(separator)

    if not admin1_agg:
        lines.append("| _No province-level data available_ |" + " — |" * (len(columns) - 1))
        return

    for key in sorted(admin1_agg.keys()):
        bucket = admin1_agg[key]
        name = bucket.get("name", key)
        districts = bucket.get("districts_affected", [])
        figs = bucket.get("figures", {})
        row = [
            name,
            str(len(districts)),
            f"{figs.get('people_affected', 0):,}" if figs.get('people_affected') else "—",
            f"{figs.get('displaced', 0):,}" if figs.get('displaced') else "—",
            f"{figs.get('deaths', 0):,}" if figs.get('deaths') else "—",
            f"{figs.get('missing', 0):,}" if figs.get('missing') else "—",
            f"{figs.get('houses_affected', 0):,}" if figs.get('houses_affected') else "—",
            f"Severity phase {bucket.get('max_severity', 0)}",
            "Assessment ongoing",
        ]
        # Pad/trim row to match columns
        while len(row) < len(columns):
            row.append("—")
        lines.append("| " + " | ".join(row[:len(columns)]) + " |")


def _render_admin2_tables(
    lines: list[str],
    *,
    ontology: HumanitarianOntologyGraph,
    admin1_agg: dict[str, dict[str, Any]],
    template: dict[str, Any],
    llm_narrative: dict[str, str],
) -> None:
    """Render per-province Admin 2 tables."""
    table_def = template.get("admin2_table", {})
    columns = table_def.get("columns", [
        "District", "Pop. Affected", "Displaced", "Deaths",
        "Missing", "Injured", "Houses Fully Destroyed",
        "Houses Partially Damaged", "Flood", "Storm Surge / Landslide",
        "Key Localities",
    ])

    if not admin1_agg:
        lines.append("_No district-level data available at this time._")
        lines.append("")
        return

    for adm1_key in sorted(admin1_agg.keys()):
        bucket = admin1_agg[adm1_key]
        province_name = bucket.get("name", adm1_key)
        lines.append(f"### {province_name}")
        lines.append("")

        districts = ontology.admin2_areas(parent=adm1_key)
        if not districts:
            # Fallback: use district names from aggregation
            district_names = bucket.get("districts_affected", [])
            if district_names:
                header = "| " + " | ".join(columns) + " |"
                sep = "|" + "|".join("---" for _ in columns) + "|"
                lines.append(header)
                lines.append(sep)
                for dn in sorted(district_names):
                    d_agg = ontology.aggregate_figures_by_admin2(admin1=adm1_key).get(
                        dn.strip().lower(), {}
                    )
                    figs = d_agg.get("figures", {})
                    row = _build_admin2_row(dn, figs, columns)
                    lines.append("| " + " | ".join(row) + " |")
            else:
                lines.append(f"_No district-level breakdown available for {province_name}._")
        else:
            header = "| " + " | ".join(columns) + " |"
            sep = "|" + "|".join("---" for _ in columns) + "|"
            lines.append(header)
            lines.append(sep)
            adm2_data = ontology.aggregate_figures_by_admin2(admin1=adm1_key)
            for d in districts:
                d_key = d.name.strip().lower()
                d_agg = adm2_data.get(d_key, {})
                figs = d_agg.get("figures", {})
                row = _build_admin2_row(d.name, figs, columns)
                lines.append("| " + " | ".join(row) + " |")

        # Province narrative from LLM
        narrative_key = f"admin2_{adm1_key}"
        if llm_narrative.get(narrative_key):
            lines.append("")
            lines.append(llm_narrative[narrative_key])
        lines.append("")


def _build_admin2_row(
    district_name: str,
    figures: dict[str, int],
    columns: list[str],
) -> list[str]:
    """Build one row for the admin 2 table."""
    def _fig(key: str) -> str:
        v = figures.get(key, 0)
        return f"{v:,}" if v else "—"

    # Map column names to figure keys
    col_map: dict[str, str] = {
        "District": district_name,
        "Pop. Affected": _fig("people_affected"),
        "Displaced": _fig("displaced"),
        "Deaths": _fig("deaths"),
        "Missing": _fig("missing"),
        "Injured": _fig("injured"),
        "Houses Fully Destroyed": _fig("houses_affected"),
        "Houses Partially Damaged": "—",
        "Flood": "—",
        "Storm Surge / Landslide": "—",
        "Key Localities": "—",
    }
    row: list[str] = []
    for col in columns:
        row.append(col_map.get(col, "—"))
    return row


def _clean_description(raw: str, max_len: int = 90) -> str:
    """Strip HTML tags, collapse whitespace, and truncate to *max_len* chars."""
    import re as _re
    # Fast HTML strip — no need for bs4 in this hot path
    text = _re.sub(r"<[^>]+>", " ", raw)
    text = _re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


_SEVERITY_LABEL: dict[int, str] = {
    1: "Minimal",
    2: "Stressed",
    3: "Crisis",
    4: "Emergency",
    5: "Catastrophe",
}


def _render_sector_section(
    lines: list[str],
    *,
    sector_key: str,
    ontology: HumanitarianOntologyGraph,
    template: dict[str, Any],
    llm_narrative: dict[str, str],
) -> None:
    """Render one sectoral analysis section with deterministic tables.

    Tables use structured fields only — raw descriptions are never dumped
    into cells.  A concise cleaned summary goes into the last column.
    """
    schemas = template.get("sector_schemas", {})
    schema = schemas.get(sector_key, {})
    table_cols = schema.get("table_columns", [])
    prompts = schema.get("narrative_prompts", [])
    need_type = _SECTOR_NEED_MAP.get(sector_key)

    # ── Sectoral table ──────────────────────────────────────────
    if table_cols:
        # Deterministic column header
        # We use: Area | Severity | # Reports | <last template col> as summary
        # If the template has ≤2 cols we just use them directly.
        use_canonical = len(table_cols) >= 3
        if use_canonical:
            display_cols = [table_cols[0], "Severity", "Reports", table_cols[-1]]
        else:
            display_cols = list(table_cols)

        lines.append("| " + " | ".join(display_cols) + " |")
        lines.append("|" + "|".join("---" for _ in display_cols) + "|")

        if need_type:
            needs = ontology.needs_by_sector(need_type)
            if needs:
                # Group by geo area for one row per area
                geo_groups: dict[str, list[NeedStatement]] = {}
                for n in needs:
                    geo_groups.setdefault(n.geo_area, []).append(n)

                for geo, group in sorted(geo_groups.items()):
                    max_sev = max(n.severity_phase for n in group)
                    sev_label = _SEVERITY_LABEL.get(max_sev, f"Phase {max_sev}")
                    report_count = str(len(group))
                    # Summary: first non-empty description, cleaned
                    descs = [n.description for n in group if n.description]
                    summary = (
                        _clean_description(descs[0])
                        if descs
                        else "See narrative below"
                    )
                    if use_canonical:
                        row = [geo, sev_label, report_count, summary]
                    else:
                        row = [geo, summary][: len(display_cols)]
                    lines.append("| " + " | ".join(row) + " |")
            else:
                lines.append(
                    "| _No sector-specific data_ |"
                    + " — |" * (len(display_cols) - 1)
                )
        else:
            lines.append(
                "| _No sector data_ |"
                + " — |" * (len(display_cols) - 1)
            )

    # ── Narrative (LLM preferred → deterministic fallback) ──────
    narrative_key = f"sectoral_{sector_key}"
    if llm_narrative.get(narrative_key):
        lines.append("")
        lines.append(llm_narrative[narrative_key])
    elif need_type:
        needs = ontology.needs_by_sector(need_type)
        if needs:
            lines.append("")
            # Bullet list of cleaned descriptions (max 5)
            for n in needs[:5]:
                if n.description:
                    lines.append(f"- {_clean_description(n.description, 160)}")
        elif prompts:
            lines.append("")
            for prompt in prompts:
                lines.append(f"- **{prompt}:** _Assessment pending._")
    elif prompts:
        lines.append("")
        for prompt in prompts:
            lines.append(f"- **{prompt}:** _Assessment pending._")


def _render_outstanding_needs(
    lines: list[str],
    *,
    sector_summary: dict[str, dict[str, Any]],
    template: dict[str, Any],
    llm_narrative: dict[str, str],
) -> None:
    """Render Outstanding Needs section."""
    table_def = template.get("outstanding_needs_table", {})
    columns = table_def.get("columns", ["Sector", "Urgent Needs", "Medium-Term Needs", "Notes"])
    sector_rows = table_def.get("rows", [
        "Shelter", "WASH", "Health", "Food", "Protection", "Education", "Logistics",
    ])

    lines.append("| " + " | ".join(columns) + " |")
    lines.append("|" + "|".join("---" for _ in columns) + "|")

    for sector_label in sector_rows:
        sector_key = sector_label.lower().replace(" ", "_")
        bucket = sector_summary.get(sector_key, {})
        count = bucket.get("count", 0)
        max_sev = bucket.get("max_severity", 0)
        urgent = f"Phase {max_sev}" if max_sev >= 3 else "Under review"
        medium = f"{count} needs identified" if count else "—"
        lines.append(f"| {sector_label} | {urgent} | {medium} | — |")

    if llm_narrative.get("outstanding_needs"):
        lines.append("")
        lines.append(llm_narrative["outstanding_needs"])


def _render_forecast(
    lines: list[str],
    *,
    ontology: HumanitarianOntologyGraph,
    template: dict[str, Any],
    llm_narrative: dict[str, str],
) -> None:
    """Render Forecast & Risk Outlook section."""
    forecast_def = template.get("forecast_structure", {})
    horizons = forecast_def.get("horizons", [
        {"label": "48-72 hour outlook", "prompts": []},
        {"label": "7-day outlook", "prompts": []},
    ])

    for horizon in horizons:
        label = horizon.get("label", "Outlook")
        prompts = horizon.get("prompts", [])
        lines.append(f"### {label}")
        lines.append("")

        # Map horizon label to risk data
        horizon_key = "48h" if "48" in label else "7d"
        risks = ontology.risks_by_horizon(horizon_key)

        if risks:
            for risk in risks:
                lines.append(f"- {risk.description}")
        elif prompts:
            for p in prompts:
                lines.append(f"- **{p}:** _Forecast data pending._")
        else:
            lines.append("- _No forecast data available._")
        lines.append("")

    if llm_narrative.get("forecast_risk"):
        lines.append(llm_narrative["forecast_risk"])


def _render_annex(
    lines: list[str],
    *,
    ontology: HumanitarianOntologyGraph,
) -> None:
    """Render the admin reference annex."""
    admin1_list = ontology.admin1_areas()
    if not admin1_list:
        lines.append("_No admin hierarchy data available._")
        return

    lines.append("| Admin 1 (Province) | Admin 2 (Districts) |")
    lines.append("|--------------------|--------------------|")
    for adm1 in admin1_list:
        districts = ontology.admin2_areas(parent=adm1.name)
        district_names = ", ".join(d.name for d in districts) or "—"
        lines.append(f"| {adm1.name} | {district_names} |")


# ── LLM narrative generation ────────────────────────────────────────

def _generate_llm_narratives(
    *,
    graph_context: dict[str, Any],
    ontology: HumanitarianOntologyGraph,
    template: dict[str, Any],
    citation_numbers: dict[str, int],
    event_name: str,
) -> dict[str, str]:
    """Generate LLM-written narratives via a two-pass approach.

    Pass 1 — Core narrative: executive summary, national impact,
             access constraints, outstanding needs, forecast/risk.
    Pass 2 — Sectoral narratives: shelter, WASH, health, food security,
             protection, education.  Runs with the Pass 1 output as
             additional context so sectoral text stays coherent.
    """
    api_key = get_openai_api_key()
    if not api_key:
        return {}

    try:
        import httpx
    except ImportError:
        return {}

    limits = template.get("limits", {})
    nat_figures = ontology.national_figures()

    # Build a compact evidence digest for the LLM
    evidence_digest = []
    for ev in graph_context.get("evidence", [])[:30]:
        entry: dict[str, Any] = {
            "title": ev.get("title", ""),
            "country": ev.get("country", ""),
            "summary": ev.get("summary", "")[:200],
            "severity": ev.get("severity", ""),
            "source": ev.get("source_label") or ev.get("connector", ""),
        }
        # Add date if available — critical for temporal attribution
        pub = ev.get("published_at") or ev.get("date") or ""
        if pub:
            entry["date"] = str(pub)[:10]  # YYYY-MM-DD
        evidence_digest.append(entry)

    common_payload = json.dumps({
        "evidence": evidence_digest,
        "national_figures": nat_figures,
        "admin1_areas": [a.name for a in ontology.admin1_areas()],
        "hazards": [h.name for h in ontology.hazards.values()],
        "sector_needs": {
            k: v.get("count", 0)
            for k, v in ontology.sector_summary().items()
        },
    })[:80000]

    attribution_rules = (
        "ATTRIBUTION RULES:\n"
        "- Cite dates when available (e.g. 'As of 12 Jan 2026…').\n"
        "- Cite the source when available (e.g. '…according to OCHA').\n"
        "- Never fabricate a date or source not present in the evidence.\n"
        "- ALWAYS include citation references using [N] notation where N is the "
        "citation number from the citation index below. Every factual claim MUST "
        "have at least one [N] reference.\n"
        "- Multiple claims from the same source can share one [N] reference.\n"
    )

    # Build citation index string for LLM
    citation_index_str = "\n".join(
        f"  [{n}] {url}" for url, n in sorted(citation_numbers.items(), key=lambda x: x[1])
    )
    citation_context = f"\nCITATION INDEX:\n{citation_index_str}\n" if citation_numbers else ""

    # ── Pass 1: Core narrative ────────────────────────────────────
    _core_keys = [
        "executive_summary", "national_impact", "access_constraints",
        "outstanding_needs", "forecast_risk",
    ]
    _core_schema = {
        "type": "object",
        "properties": {k: {"type": "string"} for k in _core_keys},
        "required": _core_keys,
        "additionalProperties": False,
    }

    core_instructions = (
        "You are writing the CORE sections of an OCHA-style Situation Analysis. "
        "Return a JSON object with the following keys: "
        + ", ".join(_core_keys) + ". "
        "Write concise, factual humanitarian prose grounded ONLY in the provided evidence. "
        "Do NOT invent figures or facts not present in evidence.\n"
        + attribution_rules
        + citation_context
        + f"Event: {event_name}\n"
        f"National figures: {json.dumps(nat_figures)}\n"
        f"Word limits: ~{limits.get('executive_summary_max_words', 500)} words for "
        f"executive_summary, ~300 words for other sections."
    )

    core_result = _call_sa_llm(
        api_key=api_key,
        instructions=core_instructions,
        payload=common_payload,
        schema=_core_schema,
        schema_name="sa_core_narratives",
    )

    # ── Pass 2: Sectoral narratives ───────────────────────────────
    _sector_keys = [
        "sectoral_shelter", "sectoral_wash", "sectoral_health",
        "sectoral_food_security", "sectoral_protection", "sectoral_education",
    ]
    _sector_schema = {
        "type": "object",
        "properties": {k: {"type": "string"} for k in _sector_keys},
        "required": _sector_keys,
        "additionalProperties": False,
    }

    # Inject Pass 1 output as context so sectors stay coherent
    sector_context = ""
    if core_result:
        sector_context = (
            "\n\nThe following core sections have already been written. "
            "Use them for context — do NOT repeat their content:\n"
            + json.dumps(core_result)[:12000]
        )

    sector_instructions = (
        "You are writing the SECTORAL sections of an OCHA-style Situation Analysis. "
        "Return a JSON object with the following keys: "
        + ", ".join(_sector_keys) + ". "
        "Write concise, factual humanitarian prose grounded ONLY in the provided evidence. "
        "Each section should focus on its specific sector (Shelter, WASH, Health, "
        "Food Security, Protection, Education).\n"
        + attribution_rules
        + citation_context
        + f"Event: {event_name}\n"
        f"Word limits: ~{limits.get('sector_max_words', 250)} words per section."
        + sector_context
    )

    sector_result = _call_sa_llm(
        api_key=api_key,
        instructions=sector_instructions,
        payload=common_payload,
        schema=_sector_schema,
        schema_name="sa_sector_narratives",
    )

    # Merge both passes
    merged: dict[str, str] = {}
    merged.update(core_result or {})
    merged.update(sector_result or {})
    return merged


def _call_sa_llm(
    *,
    api_key: str,
    instructions: str,
    payload: str,
    schema: dict,
    schema_name: str,
) -> dict[str, str] | None:
    """Make a single SA LLM call with strict JSON schema."""
    import httpx

    body = {
        "model": get_openai_model(),
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
            {"role": "user", "content": [{"type": "input_text", "text": payload}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            }
        },
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None

    text = _extract_responses_text(data)
    try:
        parsed = json.loads(text) if text else None
    except (json.JSONDecodeError, TypeError):
        parsed = _extract_json_object(text)
    if not isinstance(parsed, dict):
        return None

    return {k: str(v) for k, v in parsed.items() if isinstance(v, str)}


# NOTE: _extract_responses_text and _extract_json_object definitions
# have been moved to llm_utils.py — aliases imported at module top.


# ── Public entry point ───────────────────────────────────────────────

def write_situation_analysis(
    *,
    countries: list[str] | None = None,
    disaster_types: list[str] | None = None,
    title: str = "Situation Analysis",
    event_name: str = "",
    event_type: str = "",
    period: str = "",
    admin_hierarchy: dict[str, list[str]] | None = None,
    template_path: Path | None = None,
    use_llm: bool = False,
    limit_cycles: int = 20,
    limit_events: int = 80,
    max_age_days: int | None = None,
    output_path: Path | None = None,
    path: Path | None = None,
    quality_gate: bool = False,
) -> dict[str, Any]:
    """Top-level function: gather evidence → build ontology → render SA.

    Returns a result dict compatible with CLI JSON output.
    """
    graph_context = build_graph_context(
        countries=countries,
        disaster_types=disaster_types,
        limit_cycles=limit_cycles,
        limit_events=limit_events,
        max_age_days=max_age_days,
        path=path,
        strict_filters=True,
    )

    report_md = render_situation_analysis(
        graph_context=graph_context,
        title=title,
        event_name=event_name,
        event_type=event_type,
        period=period,
        admin_hierarchy=admin_hierarchy,
        template_path=template_path,
        use_llm=use_llm,
        quality_gate=quality_gate,
    )

    out_path = write_report_file(
        report_markdown=report_md,
        output_path=output_path,
    )

    # ── Parse quality gate scores from rendered markdown (if enabled) ──
    sa_quality: dict[str, Any] = {}
    if quality_gate:
        try:
            from .sa_quality_gate import score_situation_analysis as _score_sa
            qa = _score_sa(report_md)
            sa_quality = {
                "overall_score": qa.overall_score,
                "passed": qa.passed,
                "section_completeness": qa.section_completeness,
                "key_figure_coverage": qa.key_figure_coverage,
                "citation_accuracy": qa.citation_accuracy,
                "citation_density": qa.citation_density,
                "admin_coverage": qa.admin_coverage,
                "date_attribution": qa.date_attribution,
                "details": qa.details,
            }
        except Exception:
            pass

    return {
        "status": "ok",
        "report_path": str(out_path),
        "meta": graph_context.get("meta", {}),
        "llm_used": use_llm,
        "report_type": "situation_analysis",
        "quality_gate": sa_quality,
    }

"""GraphRAG-style report generation from persisted monitoring evidence."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlmodel import Session, select

from .config import normalize_disaster_types
from .database import EventRecord, RawItemRecord, build_engine, get_recent_cycles
from .gazetteers import country_to_iso3
from .llm_utils import (
    build_citation_numbers,
    citation_ref,
    domain_counter,
    extract_json_object,
    extract_responses_text,
)
from .settings import get_openai_api_key, get_openai_model
from .time_utils import parse_published_datetime

# Backward-compatible aliases (existing private names)
_extract_responses_text = extract_responses_text
_extract_json_object = extract_json_object
_build_citation_numbers = build_citation_numbers
_citation_ref = citation_ref
_domain_counter = domain_counter


@dataclass
class ReportEvidence:
    event_id: str
    title: str
    country: str
    country_iso3: str
    disaster_type: str
    connector: str
    source_type: str
    severity: str
    confidence: str
    summary: str
    url: str
    canonical_url: str | None
    published_at: str | None
    text: str
    corroboration_sources: int
    graph_score: float
    source_label: str


def default_report_template() -> dict[str, Any]:
    return {
        "name": "default-v1",
        "sections": {
            "executive_summary": "Executive Summary",
            "incident_highlights": "Incident Highlights",
            "source_reliability": "Source and Connector Reliability Snapshot",
            "risk_outlook": "Risk Outlook",
            "method": "Method",
            "citations": "Citations",
        },
        "limits": {
            "max_incident_highlights": 12,
            "executive_summary_max_words": 180,
            "source_reliability_max_words": 140,
            "risk_outlook_max_words": 180,
            "method_max_words": 120,
            "incident_summary_max_words": 80,
            "incident_quote_max_chars": 600,
        },
    }


def load_report_template(path: Path | None = None) -> dict[str, Any]:
    template = default_report_template()
    candidate = path or (Path.cwd() / "config" / "report_template.json")
    if not candidate.exists():
        return template
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return template
    if not isinstance(payload, dict):
        return template
    for key in ("sections", "limits"):
        if isinstance(payload.get(key), dict):
            template[key].update(payload[key])
    if isinstance(payload.get("name"), str) and payload["name"].strip():
        template["name"] = payload["name"].strip()
    return template


def build_graph_context(
    *,
    countries: list[str] | None = None,
    disaster_types: list[str] | None = None,
    limit_cycles: int = 20,
    limit_events: int = 60,
    max_age_days: int | None = None,
    path: Path | None = None,
    strict_filters: bool = True,
    country_min_events: int = 0,
    max_per_connector: int = 0,
    max_per_source: int = 0,
) -> dict[str, Any]:
    countries = [c.strip().lower() for c in (countries or []) if c.strip()]
    disaster_types = normalize_disaster_types(disaster_types or [], strict=False)

    cycles = get_recent_cycles(limit=limit_cycles, path=path)
    if not cycles:
        return {"evidence": [], "meta": {"cycles_analyzed": 0, "events_considered": 0}}

    cycle_ids = [int(c.id) for c in cycles if c.id is not None]
    engine = build_engine(path)

    with Session(engine) as session:
        events = list(
            session.exec(
                select(EventRecord)
                .where(EventRecord.cycle_id.in_(cycle_ids))
                .order_by(EventRecord.id.desc())
            )
        )
        raw_items = list(
            session.exec(
                select(RawItemRecord)
                .where(RawItemRecord.cycle_id.in_(cycle_ids))
                .order_by(RawItemRecord.id.desc())
            )
        )

    raw_by_cycle_url: dict[tuple[int, str], RawItemRecord] = {
        (int(r.cycle_id), str(r.url)): r for r in raw_items
    }

    facet_country = Counter(e.country.lower() for e in events)
    facet_disaster = Counter(e.disaster_type.lower() for e in events)
    facet_connector = Counter(e.connector.lower() for e in events)

    evidence: list[ReportEvidence] = []
    for e in events:
        country_l = e.country.lower()
        disaster_l = e.disaster_type.lower()
        if max_age_days:
            published_dt = parse_published_datetime(e.published_at)
            if published_dt and published_dt <= datetime.now(UTC) - timedelta(days=max_age_days):
                continue
        if countries and country_l not in countries:
            continue
        if disaster_types and disaster_l not in disaster_types:
            continue

        payload = raw_by_cycle_url.get((int(e.cycle_id), str(e.url)))
        text = ""
        if payload and payload.payload_json:
            try:
                parsed = json.loads(payload.payload_json)
                text = str(parsed.get("text", "") or "")
            except Exception:
                text = ""

        graph_score = float(
            e.corroboration_sources
            + facet_country[country_l]
            + facet_disaster[disaster_l]
            + 0.5 * facet_connector[e.connector.lower()]
        )
        graph_score *= _connector_weight(
            connector=e.connector,
            disaster_types=disaster_types,
        )
        evidence.append(
            ReportEvidence(
                event_id=e.event_id,
                title=e.title,
                country=e.country,
                country_iso3=getattr(e, "country_iso3", "") or country_to_iso3(e.country) or "",
                disaster_type=e.disaster_type,
                connector=e.connector,
                source_type=e.source_type,
                severity=e.severity,
                confidence=e.confidence,
                summary=e.summary,
                url=e.url,
                canonical_url=e.canonical_url,
                published_at=e.published_at,
                text=text,
                corroboration_sources=int(e.corroboration_sources),
                graph_score=round(graph_score, 3),
                source_label=_source_label_from_title(e.title),
            )
        )

    if not strict_filters and not evidence and events:
        # If filters are too narrow, return recent events for resilience.
        for e in events[:limit_events]:
            evidence.append(
                ReportEvidence(
                    event_id=e.event_id,
                    title=e.title,
                    country=e.country,
                    country_iso3=getattr(e, "country_iso3", "") or country_to_iso3(e.country) or "",
                    disaster_type=e.disaster_type,
                    connector=e.connector,
                    source_type=e.source_type,
                    severity=e.severity,
                    confidence=e.confidence,
                    summary=e.summary,
                    url=e.url,
                    canonical_url=e.canonical_url,
                    published_at=e.published_at,
                    text="",
                    corroboration_sources=int(e.corroboration_sources),
                    graph_score=float(e.corroboration_sources),
                    source_label=_source_label_from_title(e.title),
                )
            )

    evidence.sort(key=lambda x: (x.graph_score, x.severity, x.published_at or ""), reverse=True)
    evidence = _select_balanced_evidence(
        evidence=evidence,
        limit_events=limit_events,
        countries=countries,
        country_min_events=max(0, int(country_min_events or 0)),
        max_per_connector=max(0, int(max_per_connector or 0)),
        max_per_source=max(0, int(max_per_source or 0)),
    )

    by_country = Counter(e.country for e in evidence)
    by_disaster = Counter(e.disaster_type for e in evidence)
    by_connector = Counter(e.connector for e in evidence)
    by_source_type = Counter(e.source_type for e in evidence)

    return {
        "evidence": [e.__dict__ for e in evidence],
        "meta": {
            "cycles_analyzed": len(cycle_ids),
            "events_considered": len(events),
            "events_selected": len(evidence),
            "strict_filters": strict_filters,
            "country_min_events": int(country_min_events or 0),
            "max_per_connector": int(max_per_connector or 0),
            "max_per_source": int(max_per_source or 0),
            "filter_countries": countries,
            "filter_disaster_types": disaster_types,
            "by_country": dict(by_country),
            "by_disaster_type": dict(by_disaster),
            "by_connector": dict(by_connector),
            "by_source_type": dict(by_source_type),
        },
    }


def render_long_form_report(
    *,
    graph_context: dict[str, Any],
    title: str = "Disaster Intelligence Report",
    use_llm: bool = False,
    template_path: Path | None = None,
) -> str:
    evidence = graph_context.get("evidence", [])
    meta = graph_context.get("meta", {})
    generated_at = datetime.now(UTC).isoformat()
    template = load_report_template(template_path)
    if not evidence:
        return _render_no_evidence_report(
            title=title,
            generated_at=generated_at,
            template=template,
            meta=meta,
        )

    citation_numbers = _build_citation_numbers(evidence)
    domain_counts = _domain_counter(evidence)
    unique_domains = len(domain_counts)
    diversity_hhi = _diversity_hhi(domain_counts)
    llm_sections: dict[str, Any] | None = None
    if use_llm:
        llm_sections = _render_with_llm_sections(
            title=title,
            graph_context=graph_context,
            citation_numbers=citation_numbers,
            template=template,
        )

    return _render_report_template(
        title=title,
        generated_at=generated_at,
        meta=meta,
        evidence=evidence,
        citation_numbers=citation_numbers,
        domain_counts=domain_counts,
        unique_domains=unique_domains,
        diversity_hhi=diversity_hhi,
        template=template,
        llm_sections=llm_sections,
        ai_assisted=llm_sections is not None,
    )


def evaluate_report_quality(
    *,
    report_markdown: str,
    min_citation_density: float = 0.005,
    required_sections: list[str] | None = None,
    section_aliases: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    required_sections = required_sections or [
        "Executive Summary",
        "Incident Highlights",
        "Source and Connector Reliability Snapshot",
        "Risk Outlook",
        "Method",
    ]
    section_aliases = section_aliases or {
        "Executive Summary": ["Situation At A Glance"],
        "Incident Highlights": ["Incident Analysis", "Top Priority Updates"],
        "Source and Connector Reliability Snapshot": [
            "Source Reliability",
            "Source and Connector Reliability Assessment",
            "Evidence Confidence Snapshot",
        ],
        "Risk Outlook": ["72-Hour Risk Outlook", "Forward Risk and Scenario Outlook"],
        "Method": ["Method Note", "Methodology and Scope"],
    }

    text = report_markdown or ""
    words = len(re.findall(r"\b[\w/-]+\b", text))
    urls = re.findall(r"https?://[^\s)]+", text)
    citation_density = len(urls) / max(1, words)
    no_evidence_mode = "No evidence found for selected filters and cycles." in text
    incident_blocks = len(re.findall(r"(?m)^\s*\d+\.\s+\*\*.+\*\*", text))
    effective_min_citation_density = min(
        min_citation_density,
        _adaptive_min_citation_density(min_citation_density, incident_blocks),
    )

    missing_sections = [s for s in required_sections if not _has_required_section(text, s, section_aliases)]

    unsupported_blocks = _find_unsupported_incident_blocks(text)
    invalid_citation_refs = _find_invalid_citation_refs(text)
    status = "pass"
    reasons: list[str] = []
    if not no_evidence_mode and citation_density < effective_min_citation_density:
        status = "fail"
        reasons.append(
            f"citation_density {citation_density:.4f} below threshold {effective_min_citation_density:.4f}"
        )
    if missing_sections:
        status = "fail"
        reasons.append(f"missing required sections: {', '.join(missing_sections)}")
    if unsupported_blocks:
        status = "fail"
        reasons.append(f"unsupported incident blocks: {len(unsupported_blocks)}")
    if invalid_citation_refs:
        status = "fail"
        reasons.append(f"invalid citation refs: {len(invalid_citation_refs)}")

    return {
        "status": status,
        "reason": "; ".join(reasons) if reasons else "Report quality checks passed.",
        "metrics": {
            "word_count": words,
            "url_count": len(urls),
            "citation_density": round(citation_density, 6),
            "min_citation_density": min_citation_density,
            "effective_min_citation_density": round(effective_min_citation_density, 6),
            "incident_blocks_detected": incident_blocks,
            "missing_sections": missing_sections,
            "unsupported_incident_blocks": unsupported_blocks,
            "invalid_citation_refs": invalid_citation_refs,
            "no_evidence_mode": no_evidence_mode,
        },
    }


def _adaptive_min_citation_density(base_min_citation_density: float, incident_blocks: int) -> float:
    """Relax citation-density floor for very low-incident windows.

    This preserves strictness for normal reports while avoiding false fails
    when a filter-matched window has only 1-2 incidents.
    """
    if incident_blocks <= 0:
        return base_min_citation_density
    if incident_blocks == 1:
        return min(base_min_citation_density, 0.002)
    if incident_blocks == 2:
        return min(base_min_citation_density, 0.004)
    return base_min_citation_density


def write_report_file(
    *,
    report_markdown: str,
    output_path: Path | None = None,
) -> Path:
    path = output_path or (
        Path.cwd() / "reports" / f"report-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_markdown, encoding="utf-8")
    return path


def _top_labels(bucket: dict[str, int], limit: int) -> str:
    if not bucket:
        return "none"
    ordered = sorted(bucket.items(), key=lambda x: x[1], reverse=True)[:limit]
    return ", ".join(f"{k} ({v})" for k, v in ordered)


def _best_quote(text: str, fallback: str, max_chars: int = 600) -> str:
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    for s in sentences:
        if len(s) >= 30:
            return _clip_clean(s, max_chars=max_chars)
    return _clip_clean(fallback or "No quote available", max_chars=max_chars)


def _render_with_llm_sections(
    *,
    title: str,
    graph_context: dict[str, Any],
    citation_numbers: dict[str, int],
    template: dict[str, Any],
) -> dict[str, Any] | None:
    api_key = get_openai_api_key()
    if not api_key:
        return None
    try:
        import httpx
    except Exception:
        return None

    limits = template.get("limits", {})
    sections = template.get("sections", {})
    instructions = (
        "You are writing a humanitarian disaster report. Return JSON only (no markdown). "
        "Keep structure exactly as requested and stay grounded in provided evidence only. "
        "Use citation numbers provided in the map; do not invent citations.\n"
        "JSON schema:\n"
        "{"
        "\"executive_summary\": string, "
        "\"incident_highlights\": [{\"title\": string, \"summary\": string, \"severity\": string, \"confidence\": string, \"citation_number\": number}], "
        "\"source_reliability\": string, "
        "\"risk_outlook\": string, "
        "\"method\": string"
        "}\n"
        f"Word limits: executive_summary <= {limits.get('executive_summary_max_words', 180)} words; "
        f"source_reliability <= {limits.get('source_reliability_max_words', 140)} words; "
        f"risk_outlook <= {limits.get('risk_outlook_max_words', 180)} words; "
        f"method <= {limits.get('method_max_words', 120)} words; "
        f"incident summary <= {limits.get('incident_summary_max_words', 80)} words."
    )
    evidence_rows = []
    for ev in graph_context.get("evidence", []) or []:
        ev_url = str(ev.get("canonical_url") or ev.get("url", ""))
        evidence_rows.append(
            {
                "title": ev.get("title"),
                "country": ev.get("country"),
                "disaster_type": ev.get("disaster_type"),
                "severity": ev.get("severity"),
                "confidence": ev.get("confidence"),
                "summary": ev.get("summary"),
                "url": ev.get("url"),
                "canonical_url": ev.get("canonical_url"),
                "citation_number": citation_numbers.get(ev_url),
            }
        )
    payload = {
        "title": title,
        "sections": sections,
        "citation_map": {str(v): k for k, v in citation_numbers.items()},
        "meta": graph_context.get("meta", {}),
        "evidence": evidence_rows,
    }
    body = {
        "model": get_openai_model(),
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload)[:120000]}]},
        ],
    }
    try:
        with httpx.Client(timeout=40.0) as client:
            r = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None

    text = _extract_responses_text(data)
    parsed = _extract_json_object(text)
    if not isinstance(parsed, dict):
        return None
    return parsed


def _find_unsupported_incident_blocks(markdown: str) -> list[str]:
    """Return incident blocks missing citation refs."""
    lines = markdown.splitlines()
    findings: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r"^\d+\.\s+\*\*.+\*\*", line):
            window = "\n".join(lines[i : min(i + 8, len(lines))]).lower()
            if "citation:" not in window or not re.search(r"\[\d+\]", window):
                findings.append(line[:200])
        i += 1
    return findings


def _ensure_ai_assisted_banner(markdown: str) -> str:
    lines = markdown.splitlines()
    if not lines:
        return "# Disaster Intelligence Report\n\nAI Assisted: Yes\n"
    if lines[0].startswith("# "):
        if len(lines) > 1 and lines[1].strip().lower().startswith("ai assisted:"):
            return markdown if markdown.endswith("\n") else markdown + "\n"
        lines.insert(1, "")
        lines.insert(2, "AI Assisted: Yes")
    else:
        lines.insert(0, "AI Assisted: Yes")
    out = "\n".join(lines)
    return out if out.endswith("\n") else out + "\n"


# NOTE: _extract_responses_text and _extract_json_object definitions
# have been moved to llm_utils.py — aliases defined at module top.


def _render_report_template(
    *,
    title: str,
    generated_at: str,
    meta: dict[str, Any],
    evidence: list[dict[str, Any]],
    citation_numbers: dict[str, int],
    domain_counts: dict[str, int],
    unique_domains: int,
    diversity_hhi: float,
    template: dict[str, Any],
    llm_sections: dict[str, Any] | None,
    ai_assisted: bool,
) -> str:
    sections = template.get("sections", {})
    limits = template.get("limits", {})
    max_incidents = int(limits.get("max_incident_highlights", 12))
    max_quote_chars = int(limits.get("incident_quote_max_chars", 600))

    lines: list[str] = []
    lines.append(f"# {title}")
    if ai_assisted:
        lines.append("")
        lines.append("AI Assisted: Yes")
    lines.append("")
    lines.append(f"Generated at: {generated_at}")
    lines.append("")
    lines.append(f"## {sections.get('executive_summary', 'Executive Summary')}")

    if llm_sections:
        exec_text = _clip_words(
            str(llm_sections.get("executive_summary", "")),
            int(limits.get("executive_summary_max_words", 180)),
        )
        lines.append(exec_text or "No executive summary available.")
    else:
        lines.append(
            f"- Cycles analyzed: {meta.get('cycles_analyzed', 0)}; "
            f"evidence selected: {meta.get('events_selected', 0)}."
        )
        lines.append(f"- Most frequent countries: {_top_labels(meta.get('by_country', {}), 3)}.")
        lines.append(f"- Most frequent hazards: {_top_labels(meta.get('by_disaster_type', {}), 4)}.")
        lines.append(
            f"- Source diversity: {len(meta.get('by_connector', {}))} connectors, "
            f"{len(meta.get('by_source_type', {}))} source types, {unique_domains} unique source domains."
        )
    lines.append("")
    lines.append(f"## {sections.get('incident_highlights', 'Incident Highlights')}")

    if llm_sections and isinstance(llm_sections.get("incident_highlights"), list):
        highlights = llm_sections.get("incident_highlights", [])[:max_incidents]
        for i, h in enumerate(highlights, start=1):
            h_title = _normalize_text(str(h.get("title", f"Highlight {i}")))
            h_summary = _clip_words(
                str(h.get("summary", "")),
                int(limits.get("incident_summary_max_words", 80)),
            )
            h_sev = _normalize_text(str(h.get("severity", "unknown"))).lower() or "unknown"
            h_conf = _normalize_text(str(h.get("confidence", "unknown"))).lower() or "unknown"
            citation_num = int(h.get("citation_number", 0) or 0)
            citation_ref = f"[{citation_num}]" if citation_num > 0 else "[unavailable]"
            lines.append(f"{i}. **{h_title}** (severity={h_sev}, confidence={h_conf})")
            lines.append(f"   - Summary: {h_summary}")
            lines.append(f"   - Citation: {citation_ref}")
    else:
        for i, ev in enumerate(evidence[:max_incidents], start=1):
            quote = _best_quote(ev.get("text", ""), fallback=ev.get("summary", ""), max_chars=max_quote_chars)
            summary_clean = _clip_words(
                str(ev.get("summary", "")),
                int(limits.get("incident_summary_max_words", 80)),
            )
            citation_ref = _citation_ref(
                citation_numbers,
                str(ev.get("canonical_url", "") or ""),
                str(ev.get("url", "")),
            )
            lines.append(
                f"{i}. **{ev.get('title')}** "
                f"({ev.get('country')} | {ev.get('disaster_type')} | "
                f"severity={ev.get('severity')}, confidence={ev.get('confidence')}, "
                f"corroboration={ev.get('corroboration_sources')})"
            )
            lines.append(f"   - Summary: {summary_clean}")
            lines.append(f"   - Evidence quote: \"{quote}\"")
            lines.append(f"   - Citation: {citation_ref}")
    lines.append("")
    lines.append(f"## {sections.get('source_reliability', 'Source and Connector Reliability Snapshot')}")
    if llm_sections:
        lines.append(
            _clip_words(
                str(llm_sections.get("source_reliability", "")),
                int(limits.get("source_reliability_max_words", 140)),
            )
            or "No source reliability notes available."
        )
    lines.append(f"- Connectors: {_top_labels(meta.get('by_connector', {}), 6)}")
    lines.append(f"- Source types: {_top_labels(meta.get('by_source_type', {}), 6)}")
    lines.append(f"- Source domains: {_top_labels(domain_counts, 8)}")
    lines.append(f"- Diversity concentration (HHI): {diversity_hhi:.3f} (lower is better)")
    lines.append("")
    lines.append(f"## {sections.get('risk_outlook', 'Risk Outlook')}")
    if llm_sections:
        lines.append(
            _clip_words(
                str(llm_sections.get("risk_outlook", "")),
                int(limits.get("risk_outlook_max_words", 180)),
            )
            or "No risk outlook available."
        )
    else:
        high_count = sum(1 for ev in evidence if ev.get("severity") in {"high", "critical"})
        lines.append(f"- High/critical incident share in selected evidence: {high_count}/{len(evidence)}.")
        lines.append("- Operational recommendation: prioritize verification cadence on high-corroboration incidents.")
    lines.append("")
    lines.append(f"## {sections.get('method', 'Method')}")
    if llm_sections:
        lines.append(
            _clip_words(
                str(llm_sections.get("method", "")),
                int(limits.get("method_max_words", 120)),
            )
            or "No method details available."
        )
    else:
        lines.append(
            "- Retrieval uses a graph-style relevance score over persisted event facets "
            "(country, hazard, connector, corroboration), without vector embeddings."
        )
        lines.append("- Report generation defaults to deterministic rendering with optional LLM fallback.")
    lines.append("")
    lines.append(f"## {sections.get('citations', 'Citations')}")
    for url, n in sorted(citation_numbers.items(), key=lambda item: item[1]):
        lines.append(f"{n}. {url}")
    lines.append("")
    return "\n".join(lines) + "\n"


def _render_no_evidence_report(
    *,
    title: str,
    generated_at: str,
    template: dict[str, Any],
    meta: dict[str, Any],
) -> str:
    sections = template.get("sections", {})
    countries = meta.get("filter_countries", []) or []
    disasters = meta.get("filter_disaster_types", []) or []
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Generated at: {generated_at}")
    lines.append("")
    lines.append(f"## {sections.get('executive_summary', 'Executive Summary')}")
    lines.append("No evidence found for selected filters and cycles.")
    lines.append(
        f"- Cycles analyzed: {meta.get('cycles_analyzed', 0)}; "
        f"events considered: {meta.get('events_considered', 0)}; "
        f"events selected: {meta.get('events_selected', 0)}."
    )
    lines.append(f"- Country filters: {', '.join(countries) if countries else 'none'}")
    lines.append(f"- Disaster filters: {', '.join(disasters) if disasters else 'none'}")
    lines.append("")
    lines.append(f"## {sections.get('incident_highlights', 'Incident Highlights')}")
    lines.append("- No qualifying incidents matched the selected filters in the analyzed cycle window.")
    lines.append("")
    lines.append(f"## {sections.get('source_reliability', 'Source and Connector Reliability Snapshot')}")
    lines.append("- No matched records available to evaluate source reliability for this filter window.")
    lines.append("")
    lines.append(f"## {sections.get('risk_outlook', 'Risk Outlook')}")
    lines.append("- Risk outlook cannot be confidently assessed from matched evidence in this window.")
    lines.append("- Recommendation: broaden countries/disaster types or increase `--limit-cycles` and rerun.")
    lines.append("")
    lines.append(f"## {sections.get('method', 'Method')}")
    lines.append("- Strict filter mode was applied for report retrieval.")
    lines.append("- Quality gates were evaluated in no-evidence mode for this report.")
    lines.append("")
    lines.append(f"## {sections.get('citations', 'Citations')}")
    lines.append("No source citations available for this filter window.")
    lines.append("")
    return "\n".join(lines) + "\n"


# NOTE: _build_citation_numbers, _citation_ref, _domain_counter definitions
# have been moved to llm_utils.py — aliases defined at module top.


def _source_label_from_title(title: str) -> str:
    m = re.match(r"^\[(.+?)\]\s+", title or "")
    if m:
        return m.group(1).strip()
    return "unknown"


def _connector_weight(*, connector: str, disaster_types: list[str]) -> float:
    base = {
        "reliefweb": 1.35,
        "un_humanitarian_feeds": 1.30,
        "government_feeds": 1.15,
        "ngo_feeds": 1.10,
        "local_news_feeds": 0.95,
    }.get((connector or "").lower(), 1.0)
    humanitarian_focus = any(
        d in {"conflict emergency", "cyclone/storm", "flood", "landslide", "heatwave", "wildfire"}
        for d in disaster_types
    )
    if humanitarian_focus and (connector or "").lower() in {"reliefweb", "un_humanitarian_feeds"}:
        return base + 0.1
    return base


def _select_balanced_evidence(
    *,
    evidence: list[ReportEvidence],
    limit_events: int,
    countries: list[str],
    country_min_events: int,
    max_per_connector: int,
    max_per_source: int,
) -> list[ReportEvidence]:
    if not evidence:
        return []

    by_id = {e.event_id: e for e in evidence}
    selected: list[ReportEvidence] = []
    used: set[str] = set()
    connector_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    country_counts: Counter[str] = Counter()

    def source_key(ev: ReportEvidence) -> str:
        if ev.source_label and ev.source_label.lower() != "unknown":
            return ev.source_label
        return urlparse(ev.canonical_url or ev.url).netloc.lower() or "unknown"

    def can_take(ev: ReportEvidence) -> bool:
        if max_per_connector > 0 and connector_counts[ev.connector] >= max_per_connector:
            return False
        if max_per_source > 0 and source_counts[source_key(ev)] >= max_per_source:
            return False
        return True

    def take(ev: ReportEvidence) -> None:
        selected.append(ev)
        used.add(ev.event_id)
        connector_counts[ev.connector] += 1
        source_counts[source_key(ev)] += 1
        country_counts[ev.country.lower()] += 1

    if country_min_events > 0 and countries:
        for country in countries:
            needed = country_min_events
            for ev in evidence:
                if len(selected) >= limit_events:
                    break
                if ev.event_id in used:
                    continue
                if ev.country.lower() != country:
                    continue
                if not can_take(ev):
                    continue
                take(ev)
                needed -= 1
                if needed <= 0:
                    break

    for ev in evidence:
        if len(selected) >= limit_events:
            break
        if ev.event_id in used:
            continue
        if not can_take(ev):
            continue
        take(ev)

    # Stable order by score after constrained selection.
    selected.sort(key=lambda x: (x.graph_score, x.severity, x.published_at or ""), reverse=True)
    return selected


def _diversity_hhi(domain_counts: dict[str, int]) -> float:
    total = sum(domain_counts.values())
    if total <= 0:
        return 0.0
    return sum((count / total) ** 2 for count in domain_counts.values())


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clip_clean(value: str, max_chars: int = 600) -> str:
    clean = _normalize_text(value)
    if len(clean) <= max_chars:
        return clean
    clipped = clean[: max_chars - 1].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."

def _clip_words(value: str, max_words: int) -> str:
    clean = _normalize_text(value)
    if max_words <= 0 or not clean:
        return clean
    words = clean.split(" ")
    if len(words) <= max_words:
        return clean
    return " ".join(words[:max_words]).rstrip() + "..."


def _has_required_section(text: str, section: str, aliases: dict[str, list[str]]) -> bool:
    candidates = [section] + aliases.get(section, [])
    lowered = text.lower()
    for name in candidates:
        if f"## {name}".lower() in lowered:
            return True
    return False


def _find_invalid_citation_refs(markdown: str) -> list[int]:
    refs = {int(m.group(1)) for m in re.finditer(r"\[(\d+)\]", markdown)}
    citation_lines = {
        int(m.group(1))
        for m in re.finditer(r"(?m)^\s*(\d+)\.\s+https?://\S+\s*$", markdown)
    }
    invalid = sorted(n for n in refs if n not in citation_lines)
    return invalid

"""GraphRAG-style report generation from persisted monitoring evidence."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlmodel import Session, select

from .database import EventRecord, RawItemRecord, build_engine, get_recent_cycles
from .settings import get_openai_api_key, get_openai_model


@dataclass
class ReportEvidence:
    event_id: str
    title: str
    country: str
    disaster_type: str
    connector: str
    source_type: str
    severity: str
    confidence: str
    summary: str
    url: str
    published_at: str | None
    text: str
    corroboration_sources: int
    graph_score: float


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
    path: Path | None = None,
    strict_filters: bool = True,
) -> dict[str, Any]:
    countries = [c.strip().lower() for c in (countries or []) if c.strip()]
    disaster_types = [d.strip().lower() for d in (disaster_types or []) if d.strip()]

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
        evidence.append(
            ReportEvidence(
                event_id=e.event_id,
                title=e.title,
                country=e.country,
                disaster_type=e.disaster_type,
                connector=e.connector,
                source_type=e.source_type,
                severity=e.severity,
                confidence=e.confidence,
                summary=e.summary,
                url=e.url,
                published_at=e.published_at,
                text=text,
                corroboration_sources=int(e.corroboration_sources),
                graph_score=round(graph_score, 3),
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
                    disaster_type=e.disaster_type,
                    connector=e.connector,
                    source_type=e.source_type,
                    severity=e.severity,
                    confidence=e.confidence,
                    summary=e.summary,
                    url=e.url,
                    published_at=e.published_at,
                    text="",
                    corroboration_sources=int(e.corroboration_sources),
                    graph_score=float(e.corroboration_sources),
                )
            )

    evidence.sort(key=lambda x: (x.graph_score, x.severity, x.published_at or ""), reverse=True)
    evidence = evidence[:limit_events]

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

    missing_sections = [s for s in required_sections if not _has_required_section(text, s, section_aliases)]

    unsupported_blocks = _find_unsupported_incident_blocks(text)
    invalid_citation_refs = _find_invalid_citation_refs(text)
    status = "pass"
    reasons: list[str] = []
    if not no_evidence_mode and citation_density < min_citation_density:
        status = "fail"
        reasons.append(
            f"citation_density {citation_density:.4f} below threshold {min_citation_density:.4f}"
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
            "missing_sections": missing_sections,
            "unsupported_incident_blocks": unsupported_blocks,
            "invalid_citation_refs": invalid_citation_refs,
            "no_evidence_mode": no_evidence_mode,
        },
    }


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
        ev_url = str(ev.get("url", ""))
        evidence_rows.append(
            {
                "title": ev.get("title"),
                "country": ev.get("country"),
                "disaster_type": ev.get("disaster_type"),
                "severity": ev.get("severity"),
                "confidence": ev.get("confidence"),
                "summary": ev.get("summary"),
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


def _extract_responses_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    chunks: list[str] = []
    for out in payload.get("output", []) or []:
        for content in out.get("content", []) or []:
            if content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
    return "\n\n".join(chunks)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except Exception:
            return None


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
            citation_ref = _citation_ref(citation_numbers, str(ev.get("url", "")))
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


def _build_citation_numbers(evidence: list[dict[str, Any]]) -> dict[str, int]:
    citations: dict[str, int] = {}
    for ev in evidence:
        url = str(ev.get("url", "")).strip()
        if not url:
            continue
        if url not in citations:
            citations[url] = len(citations) + 1
    return citations


def _citation_ref(citation_numbers: dict[str, int], url: str) -> str:
    n = citation_numbers.get(url)
    return f"[{n}]" if n else "[unavailable]"


def _domain_counter(evidence: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for ev in evidence:
        raw_url = str(ev.get("url", "")).strip()
        host = urlparse(raw_url).netloc.lower()
        if host:
            counts[host] += 1
    return dict(counts)


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

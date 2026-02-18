"""GraphRAG-style report generation from persisted monitoring evidence."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from .database import EventRecord, RawItemRecord, build_engine, default_db_path, get_recent_cycles
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


def build_graph_context(
    *,
    countries: list[str] | None = None,
    disaster_types: list[str] | None = None,
    limit_cycles: int = 20,
    limit_events: int = 60,
    path: Path | None = None,
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

    if not evidence and events:
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
) -> str:
    evidence = graph_context.get("evidence", [])
    meta = graph_context.get("meta", {})
    generated_at = datetime.now(UTC).isoformat()
    if not evidence:
        return (
            f"# {title}\n\n"
            f"Generated at: {generated_at}\n\n"
            "No evidence found for selected filters and cycles.\n"
        )

    if use_llm:
        llm_text = _render_with_llm(graph_context=graph_context, title=title)
        if llm_text:
            return llm_text

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Generated at: {generated_at}")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(
        f"- Cycles analyzed: {meta.get('cycles_analyzed', 0)}; "
        f"evidence selected: {meta.get('events_selected', 0)}."
    )
    lines.append(
        f"- Most frequent countries: {_top_labels(meta.get('by_country', {}), 3)}."
    )
    lines.append(
        f"- Most frequent hazards: {_top_labels(meta.get('by_disaster_type', {}), 4)}."
    )
    lines.append("")
    lines.append("## Incident Highlights")
    for i, ev in enumerate(evidence[:12], start=1):
        quote = _best_quote(ev.get("text", ""), fallback=ev.get("summary", ""))
        lines.append(
            f"{i}. **{ev.get('title')}** "
            f"({ev.get('country')} | {ev.get('disaster_type')} | "
            f"severity={ev.get('severity')}, confidence={ev.get('confidence')}, "
            f"corroboration={ev.get('corroboration_sources')})"
        )
        lines.append(f"   - Summary: {ev.get('summary')}")
        lines.append(f"   - Evidence quote: \"{quote}\"")
        lines.append(f"   - Source: {ev.get('url')}")
    lines.append("")
    lines.append("## Source and Connector Reliability Snapshot")
    lines.append(f"- Connectors: {_top_labels(meta.get('by_connector', {}), 6)}")
    lines.append(f"- Source types: {_top_labels(meta.get('by_source_type', {}), 6)}")
    lines.append("")
    lines.append("## Risk Outlook")
    high_count = sum(1 for ev in evidence if ev.get("severity") in {"high", "critical"})
    lines.append(
        f"- High/critical incident share in selected evidence: {high_count}/{len(evidence)}."
    )
    lines.append(
        "- Operational recommendation: prioritize verification cadence on high-corroboration incidents."
    )
    lines.append("")
    lines.append("## Method")
    lines.append(
        "- Retrieval uses a graph-style relevance score over persisted event facets "
        "(country, hazard, connector, corroboration), without vector embeddings."
    )
    lines.append(
        "- Report generation defaults to deterministic rendering with optional LLM fallback."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def evaluate_report_quality(
    *,
    report_markdown: str,
    min_citation_density: float = 0.005,
    required_sections: list[str] | None = None,
) -> dict[str, Any]:
    required_sections = required_sections or [
        "Executive Summary",
        "Incident Highlights",
        "Source and Connector Reliability Snapshot",
        "Risk Outlook",
        "Method",
    ]

    text = report_markdown or ""
    words = len(re.findall(r"\b[\w/-]+\b", text))
    urls = re.findall(r"https?://[^\s)]+", text)
    citation_density = len(urls) / max(1, words)

    missing_sections = [
        s for s in required_sections if f"## {s}".lower() not in text.lower()
    ]

    unsupported_blocks = _find_unsupported_incident_blocks(text)
    status = "pass"
    reasons: list[str] = []
    if citation_density < min_citation_density:
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
        },
    }


def write_report_file(
    *,
    report_markdown: str,
    output_path: Path | None = None,
) -> Path:
    path = output_path or (
        default_db_path().parent / "reports" / f"report-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_markdown, encoding="utf-8")
    return path


def _top_labels(bucket: dict[str, int], limit: int) -> str:
    if not bucket:
        return "none"
    ordered = sorted(bucket.items(), key=lambda x: x[1], reverse=True)[:limit]
    return ", ".join(f"{k} ({v})" for k, v in ordered)


def _best_quote(text: str, fallback: str) -> str:
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    for s in sentences:
        if len(s) >= 30:
            return s[:220]
    return (fallback or "No quote available")[:220]


def _render_with_llm(*, graph_context: dict[str, Any], title: str) -> str | None:
    api_key = get_openai_api_key()
    if not api_key:
        return None
    try:
        import httpx
    except Exception:
        return None

    instructions = (
        "Write a long-form humanitarian incident report in markdown. "
        "Stay grounded in supplied JSON only. Include sections: Executive Summary, "
        "Incident Highlights, Source Reliability, Risk Outlook, Method. "
        "For each incident highlight, include source URL."
    )
    payload = {"title": title, "graph_context": graph_context}
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

    text = data.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip() + "\n"
    return None


def _find_unsupported_incident_blocks(markdown: str) -> list[str]:
    """Return incident blocks missing source URLs."""
    lines = markdown.splitlines()
    findings: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if re.match(r"^\d+\.\s+\*\*.+\*\*", line):
            window = "\n".join(lines[i : min(i + 8, len(lines))]).lower()
            if ("source:" not in window) or ("http://" not in window and "https://" not in window):
                findings.append(line[:200])
        i += 1
    return findings

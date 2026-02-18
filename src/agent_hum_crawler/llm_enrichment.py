"""Optional LLM enrichment with strict citation locking and fallback safety."""

from __future__ import annotations

import json
import re
from typing import Callable

import httpx

from .models import EventCitation, ProcessedEvent, RawSourceItem
from .settings import get_openai_api_key, get_openai_model


def enrich_events_with_llm(
    events: list[ProcessedEvent],
    raw_items: list[RawSourceItem],
    *,
    complete_fn: Callable[[ProcessedEvent, str], dict | None] | None = None,
) -> tuple[list[ProcessedEvent], dict]:
    by_url = {str(item.url): item for item in raw_items}
    run_complete = complete_fn or _default_complete
    enriched: list[ProcessedEvent] = []
    enriched_count = 0
    fallback_count = 0
    attempted_count = 0
    provider_error_count = 0
    validation_fail_count = 0
    insufficient_text_count = 0

    for event in events:
        item = by_url.get(str(event.url))
        text = (item.text if item else "") or ""
        if len(text.strip()) < 80:
            insufficient_text_count += 1
            fallback_count += 1
            enriched.append(event)
            continue

        attempted_count += 1
        try:
            candidate = run_complete(event, text)
        except Exception:
            provider_error_count += 1
            candidate = None

        validated = _validate_candidate(candidate, source_url=str(event.url), source_text=text)
        if not validated:
            validation_fail_count += 1
            fallback_count += 1
            enriched.append(event)
            continue

        summary, severity, confidence, citations = validated
        enriched.append(
            event.model_copy(
                update={
                    "summary": summary[:320].strip(),
                    "severity": severity,
                    "confidence": confidence,
                    "llm_enriched": True,
                    "citations": citations,
                }
            )
        )
        enriched_count += 1

    return enriched, {
        "enabled": True,
        "attempted_count": attempted_count,
        "enriched_count": enriched_count,
        "fallback_count": fallback_count,
        "provider_error_count": provider_error_count,
        "validation_fail_count": validation_fail_count,
        "insufficient_text_count": insufficient_text_count,
    }


def _default_complete(event: ProcessedEvent, source_text: str) -> dict | None:
    api_key = get_openai_api_key()
    if not api_key:
        return None

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "severity", "confidence", "citations"],
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 320},
            "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "citations": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["url", "quote", "quote_start", "quote_end"],
                    "properties": {
                        "url": {"type": "string"},
                        "quote": {"type": "string", "minLength": 8},
                        "quote_start": {"type": "integer", "minimum": 0},
                        "quote_end": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
    }

    instructions = (
        "You are calibrating one disaster event from source text. "
        "Return JSON only. Summary must be factual and concise. "
        "Do not invent facts. Citations must include exact quote spans from source text "
        "with zero-based quote_start and quote_end indexes, and quote must exactly match "
        "source_text[quote_start:quote_end]."
    )
    user_payload = {
        "event": {
            "title": event.title,
            "country": event.country,
            "disaster_type": event.disaster_type,
            "severity_guess": event.severity,
            "confidence_guess": event.confidence,
            "url": str(event.url),
        },
        "source_text": source_text[:10000],
    }

    body = {
        "model": get_openai_model(),
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user_payload)}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "event_enrichment",
                "schema": schema,
                "strict": True,
            }
        },
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
        payload = response.json()

    text = payload.get("output_text")
    if not text:
        text = _extract_text_from_output(payload)
    if not text:
        return None
    return json.loads(text)


def _extract_text_from_output(payload: dict) -> str:
    blocks = payload.get("output", []) or []
    fragments: list[str] = []
    for block in blocks:
        for content in block.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                fragments.append(text)
    return "".join(fragments).strip()


def _validate_candidate(
    candidate: dict | None,
    *,
    source_url: str,
    source_text: str,
) -> tuple[str, str, str, list[EventCitation]] | None:
    if not isinstance(candidate, dict):
        return None
    summary = str(candidate.get("summary", "")).strip()
    severity = str(candidate.get("severity", "")).strip()
    confidence = str(candidate.get("confidence", "")).strip()
    raw_citations = candidate.get("citations", [])

    if not summary or severity not in {"low", "medium", "high", "critical"}:
        return None
    if confidence not in {"low", "medium", "high"}:
        return None
    if not isinstance(raw_citations, list) or not raw_citations:
        return None

    citations: list[EventCitation] = []
    for citation in raw_citations:
        if not isinstance(citation, dict):
            return None
        url = str(citation.get("url", "")).strip()
        quote = str(citation.get("quote", "")).strip()
        quote_start = citation.get("quote_start")
        quote_end = citation.get("quote_end")
        if not url or not quote:
            return None
        if url != source_url:
            return None
        if not isinstance(quote_start, int) or not isinstance(quote_end, int):
            return None
        resolved = _resolve_quote_span(source_text, quote, quote_start, quote_end)
        if not resolved:
            return None
        quote_start, quote_end, exact_slice = resolved
        citations.append(
            EventCitation(
                url=url,
                quote=exact_slice,
                quote_start=quote_start,
                quote_end=quote_end,
            )
        )

    return summary, severity, confidence, citations


def _resolve_quote_span(
    source_text: str,
    quote: str,
    quote_start: int,
    quote_end: int,
) -> tuple[int, int, str] | None:
    # 1) strict pass: provided indices are correct
    if 0 <= quote_start < quote_end <= len(source_text):
        slice_text = source_text[quote_start:quote_end]
        if slice_text == quote:
            return quote_start, quote_end, slice_text

    # 2) exact lookup by quote content
    idx = source_text.find(quote)
    if idx >= 0:
        end = idx + len(quote)
        return idx, end, source_text[idx:end]

    # 3) tolerant lookup: allow whitespace variations and smart-quote normalization
    normalized_quote = _normalize_quotes(quote).strip()
    if not normalized_quote:
        return None
    tokens = [t for t in normalized_quote.split() if t]
    if not tokens:
        return None
    pattern = r"\s+".join(re.escape(tok) for tok in tokens)
    for candidate_text in (source_text, _normalize_quotes(source_text)):
        match = re.search(pattern, candidate_text)
        if match:
            if candidate_text is source_text:
                start, end = match.start(), match.end()
                return start, end, source_text[start:end]
            # map normalized-text match back by replaying on original with token pattern
            rematch = re.search(pattern, _normalize_quotes(source_text))
            if rematch:
                start, end = rematch.start(), rematch.end()
                return start, end, source_text[start:end]
    return None


def _normalize_quotes(text: str) -> str:
    return (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )

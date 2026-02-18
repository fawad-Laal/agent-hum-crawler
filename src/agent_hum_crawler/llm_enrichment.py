"""Optional LLM enrichment with strict citation locking and fallback safety."""

from __future__ import annotations

import json
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

    for event in events:
        item = by_url.get(str(event.url))
        text = (item.text if item else "") or ""
        if len(text.strip()) < 80:
            fallback_count += 1
            enriched.append(event)
            continue

        try:
            candidate = run_complete(event, text)
        except Exception:
            candidate = None

        validated = _validate_candidate(candidate, source_url=str(event.url), source_text=text)
        if not validated:
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

    return enriched, {"enabled": True, "enriched_count": enriched_count, "fallback_count": fallback_count}


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
                    "required": ["url", "quote"],
                    "properties": {
                        "url": {"type": "string"},
                        "quote": {"type": "string", "minLength": 8},
                    },
                },
            },
        },
    }

    instructions = (
        "You are calibrating one disaster event from source text. "
        "Return JSON only. Summary must be factual and concise. "
        "Citations must quote exact spans from the source text."
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

    normalized_text = " ".join(source_text.split()).lower()
    citations: list[EventCitation] = []
    for citation in raw_citations:
        if not isinstance(citation, dict):
            return None
        url = str(citation.get("url", "")).strip()
        quote = str(citation.get("quote", "")).strip()
        if not url or not quote:
            return None
        if url != source_url:
            return None
        if " ".join(quote.split()).lower() not in normalized_text:
            return None
        citations.append(EventCitation(url=url, quote=quote))

    return summary, severity, confidence, citations

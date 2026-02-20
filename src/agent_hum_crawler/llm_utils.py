"""Shared LLM utility functions.

Extracts common OpenAI Responses-API helpers that were previously
duplicated across reporting.py and situation_analysis.py.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any
from urllib.parse import urlparse


# ── OpenAI Responses-API helpers ─────────────────────────────────────

def extract_responses_text(payload: dict[str, Any]) -> str:
    """Extract text from OpenAI Responses API output.

    Handles both the top-level ``output_text`` shorthand and the full
    ``output[].content[]`` structure.
    """
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


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse a JSON object from potentially fenced markdown text.

    Strips ````json`` / ```` fences, then falls back to scanning for
    the first ``{...}`` block.
    """
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


# ── Citation helpers ─────────────────────────────────────────────────

def build_citation_numbers(evidence: list[dict[str, Any]]) -> dict[str, int]:
    """Assign sequential citation numbers to unique evidence URLs.

    Returns a mapping from URL → 1-based citation number.
    """
    citations: dict[str, int] = {}
    for ev in evidence:
        url = str(ev.get("canonical_url") or ev.get("url", "")).strip()
        if not url:
            continue
        if url not in citations:
            citations[url] = len(citations) + 1
    return citations


def citation_ref(
    citation_numbers: dict[str, int],
    canonical_url: str | None,
    url: str,
) -> str:
    """Return ``[N]`` citation reference string for a URL."""
    n = citation_numbers.get(canonical_url or url)
    return f"[{n}]" if n else "[unavailable]"


def domain_counter(evidence: list[dict[str, Any]]) -> dict[str, int]:
    """Count how many evidence items belong to each domain."""
    counts: Counter[str] = Counter()
    for ev in evidence:
        raw_url = str(ev.get("canonical_url") or ev.get("url", "")).strip()
        host = urlparse(raw_url).netloc.lower()
        if host:
            counts[host] += 1
    return dict(counts)

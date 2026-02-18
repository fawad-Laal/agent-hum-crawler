# LLM Intelligence Layer v1

Date: 2026-02-18
Status: Planned

## Purpose
Introduce an optional LLM layer to improve extraction quality and calibration, while keeping deterministic fallback behavior.

## Scope
1. Extraction and summary from full text
- Use full article text (`rawitemrecord.payload_json.text`) to generate concise incident summaries.
- Keep summaries grounded in source text only.

2. Severity/confidence calibration by LLM
- LLM proposes severity/confidence using structured output schema.
- Rule-based engine remains the baseline and safety net.

3. Citation-locked outputs (URL + quote spans)
- Every LLM-generated claim must include:
  - source URL
  - direct quote span(s) from source text
- Claims without citation evidence are rejected.

4. Fallback when LLM unavailable
- On timeout, provider error, or invalid structured output:
  - skip LLM enrichment
  - use current deterministic rules (`dedupe.py`) and continue cycle
- Mark cycle metadata with `llm_enrichment_used=false`.

## Non-Goals (v1)
- Autonomous decision making without source-backed evidence.
- Replacing deterministic dedupe/change detection logic.

## Acceptance Criteria
- LLM enrichment can be enabled/disabled by config flag.
- 100% of LLM-enriched alerts include URL + quote spans.
- Pipeline completes successfully when LLM fails (graceful fallback).
- Pilot report includes enrichment usage metrics and fallback counts.

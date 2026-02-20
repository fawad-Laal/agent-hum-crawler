# LLM Intelligence Layer v1

Date: 2026-02-20
Status: In progress (GraphRAG report layer + Situation Analysis engine implemented)

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

5. GraphRAG long-form reporting from persisted evidence (no vector store dependency)
- Build graph-style retrieval context from SQLite events using shared facets:
  - country
  - disaster_type
  - connector
  - corroboration strength
- Generate long-form report from retrieved evidence with deterministic rendering first.
- Optionally apply LLM final drafting on top of graph-retrieved context.
- Persist report outputs for operational review.

Implemented in this phase:
- `src/agent_hum_crawler/reporting.py`
- CLI command: `write-report`
- test coverage: `tests/test_reporting.py`

Added quality gates for long-form report production behavior:
- Citation density threshold (`min_citation_density`).
- Section completeness checks:
  - Executive Summary
  - Incident Highlights
  - Source and Connector Reliability Snapshot
  - Risk Outlook
  - Method
- Unsupported-claim checks for incident blocks missing source URLs.
- Enforce mode in CLI:
  - `write-report --enforce-report-quality`
- E2E gate enforcement in `scripts/e2e_gate.py`.

## Non-Goals (v1)
- Autonomous decision making without source-backed evidence.
- Replacing deterministic dedupe/change detection logic.

## 6. Humanitarian Ontology Graph (New)
Build a structured knowledge graph from persisted evidence for typed retrieval and analysis.

Implemented components:
- `src/agent_hum_crawler/graph_ontology.py`:
  - `HumanitarianOntologyGraph` — in-memory typed graph with nodes for hazards, impacts, needs, responses, risks, and admin areas.
  - Multi-pattern NLP figure extraction (`_extract_figures`) with 4 complementary regex patterns:
    - Standard `NUM keyword` (e.g. "48,000 displaced")
    - Death toll verb patterns (e.g. "death toll rises to 59", "kills 4")
    - Quantifier patterns (e.g. "at least 52 dead", "over 800,000 affected")
    - Sentence-level death patterns (e.g. "59 killed in the storm")
  - `max()` accumulation to prevent double-counting across overlapping patterns.
  - Automatic classification of impact types (people/housing/infrastructure/agriculture/services).
  - Automatic classification of need types (shelter, WASH, health, food security, protection, education, logistics).
  - Hazard categorization mapping (geophysical, hydrological, meteorological, climatological, biological).
  - Admin area detection from text using fuzzy string matching against gazetteers.
  - Country gazetteer system (`COUNTRY_GAZETTEERS`) with admin1 → admin2 mappings:
    - Madagascar: 22 provinces, 100+ districts
    - Mozambique: 10 provinces, 50+ districts
  - Auto-detection of countries from evidence and dynamic gazetteer loading.
  - Aggregation methods: `national_figures()`, `aggregate_figures_by_admin1()`, `sector_summary()`, `risks_by_horizon()`.

## 7. OCHA-Style Situation Analysis (New)
Full-section humanitarian Situation Analysis renderer following OCHA reporting standards.

Implemented components:
- `src/agent_hum_crawler/situation_analysis.py`:
  - 15-section report structure:
    1. Executive Summary (event card + key figures)
    2. National Impact Overview (table + narrative)
    3. Province-Level (Admin 1) Impact Summary
    4. District-Level (Admin 2) Detail Tables
    5-10. Sectoral Analyses (Shelter, WASH, Health, Food Security, Protection, Education)
    11. Access Constraints
    12. Outstanding Needs & Gaps
    13. Forecast & Risk Outlook
    14. Admin Reference Annex
    15. Sources and References
  - Template-driven from `config/report_template.situation_analysis.json`.
  - Deterministic rendering path fills tables and narratives from ontology graph without LLM.
  - Optional LLM narrative generation for all sections using structured JSON output.
  - Auto-inference of event name from evidence (e.g. "Cyclone Gezani" from headlines).
  - Auto-inference of disaster type (e.g. "cyclone" → "Tropical Cyclone").
  - Dynamic access constraint extraction via keyword patterns (road damage, bridge collapse, isolation).
  - Evidence-based sector narratives map need descriptions to prompt slots.
  - CLI: `write-situation-analysis` subcommand.
  - Dashboard API: `POST /api/write-situation-analysis`.
  - Frontend: SA form with collapsible parameters and one-click generation.

## 8. Multi-Agent Architecture (Planned — v2)

> **Status update (2026-02-20):** The multi-agent approach described below has been **superseded** by the
> **Project Clarity** (Reduced++ Architecture) — a simpler deterministic pipeline with schema-locked LLM enrichment.
> See: `docs/roadmap/project-clarity-roadmap.md` (active roadmap).
> The quality defects listed in §8.1 are addressed by Reduced++ Phases 1-2.

Analysis document: `docs/analysis/sa-improvement-analysis.md`

### 8.1 Identified SA Quality Issues (from Ethiopia analysis, Feb 2026)
- Sector tables dump raw evidence text instead of synthesized content (`_render_sector_section()` root cause).
- Event name inference only matches named storms — fails for conflict/epidemic/drought.
- Only 2 country gazetteers (Madagascar, Mozambique) — no admin detection for Ethiopia, Somalia, Sudan, etc.
- Raw evidence in forecasts instead of synthesized risk outlook.
- No date awareness — evidence dates not passed to LLM or rendered in output.
- ReliefWeb PDFs catalogued but never extracted (Flash Updates, SitReps missed).
- Figure deduplication absent across evidence items (same figure from 2 sources = doubled).
- Single-shot SA LLM call with no JSON schema enforcement.
- Country substring matching bug (Niger matches Nigeria).

### 8.2 Proposed Multi-Agent Pipeline
1. **OCR Extraction Agent** — Docling (free, MIT) + Tesseract fallback for ReliefWeb PDFs
2. **Evidence Triage Agent** — Date normalization, geographic NER, relevance scoring, dedup (gpt-4.1-mini)
3. **Entity Linking Agent** — Cross-source figure deduplication, entity resolution (gpt-4.1-mini)
4. **Sector Analyst Agents** (6 parallel) — OCHA-style sector analysis with strict JSON schema (gpt-4.1)
5. **Synthesis / QA Agent** — Executive summary, cross-reference, consistency check (gpt-4.1)

### 8.3 Model Selection Strategy
- `gpt-4.1-mini`: Classification and triage tasks (cheap, fast)
- `gpt-4.1`: Synthesis and writing tasks (highest quality for executive-facing output)
- Per-agent model selection via environment variables (`OPENAI_MODEL_SECTOR`, `OPENAI_MODEL_SYNTHESIS`, etc.)

### 8.4 Graph RAG Enhancements
- Temporal layer on all graph nodes (published_at, event_date, data_cutoff, validity_window)
- Figure deduplication using semantic similarity (same figure from N sources → single canonical figure)
- Multi-impact per evidence item (current: 1 ImpactObservation per evidence)
- Expanded gazetteers: Ethiopia, Somalia, Sudan, South Sudan, DRC, Afghanistan, Yemen, Syria
- Source credibility tiers (Tier 1: OCHA/UN, Tier 2: NGO/IFRC, Tier 3: media)
- Dynamic gazetteer from LLM NER extractions

### 8.5 Implementation Phases
- Phase 1 (Quick Wins): Fix event inference, add Ethiopia gazetteer, add dates to digest, add JSON schema — 1-2 days
- Phase 2 (OCR Pipeline): Docling integration, ReliefWeb PDF extraction, pagination — 3-5 days
- Phase 3 (Multi-Agent): Agent base class, triage/entity/sector/synthesis agents — 5-8 days
- Phase 4 (Graph RAG Deep): Temporal layer, figure dedup, multi-impact, expanded gazetteers — 5-7 days
- Phase 5 (Polish): Updated specs, SA quality metrics, E2E regression tests — 2-3 days

## 9. Remaining Work (Current)
- Province-level figure distribution (distribute national totals to admin1 based on geo-mentions in evidence).
- Full-article content fetching in crawl pipeline to supplement short RSS snippet text.
- Forecast/risk data extraction from evidence.
- Ontology figure persistence in DB for cross-report trend analysis.
- ~~Multi-agent architecture rollout~~ → Superseded by Project Clarity (`docs/roadmap/project-clarity-roadmap.md`).

## Acceptance Criteria
- LLM enrichment can be enabled/disabled by config flag.
- 100% of LLM-enriched alerts include URL + quote spans.
- Pipeline completes successfully when LLM fails (graceful fallback).
- Pilot report includes enrichment usage metrics and fallback counts.
- SA sector tables show synthesized content, not raw evidence text.
- SA output includes "as of" dating on all quantitative figures.
- ReliefWeb PDF content is extracted and integrated into evidence pipeline.
- Figures deduplicated across sources — national totals not inflated.

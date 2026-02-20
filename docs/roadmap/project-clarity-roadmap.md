# Project Clarity — SA Reduced++ Implementation Roadmap

Date: 2026-02-20
Status: **Active**
Codename: **Project Clarity**
Supersedes: Initial Multi-Agent Proposal (`docs/analysis/sa-improvement-analysis.md` §3)
Predecessor: MVP Roadmap (`docs/roadmap/archive/mvp-roadmap.md` — Closed, all milestones delivered)

---

## 1. Executive Summary

This document defines the **Reduced++ Architecture** for the Situation Analysis pipeline.

**Objective — eliminate every quality defect identified in the Ethiopia SA root-cause analysis:**

| # | Defect | Fix |
|---|--------|-----|
| 1 | Raw evidence leaks into sector tables | Deterministic canonical tables + schema-locked LLM narratives |
| 2 | "Unknown Event" for non-storm crises | Expanded event-name inference (conflict, epidemic, drought) |
| 3 | Empty admin tables for Ethiopia | Ethiopia gazetteer + P-code normalization |
| 4 | Raw text in forecasts | Synthesized risk outlook via schema-locked LLM pass |
| 5 | No date awareness | Temporal layer on all graph nodes + "as of" rendering |
| 6 | PDFs never extracted | Docling OCR integration in ReliefWeb connector |
| 7 | Figure deduplication absent | Deterministic clustering (same metric + geo + scope + window) |
| 8 | No JSON schema on SA LLM | Strict `json_schema` on every LLM call |
| 9 | Niger/Nigeria substring bug | ISO3 + P-code normalization, word-boundary matching |

**Architecture principle:**

> Deterministic ingestion → Schema-locked enrichment → Deterministic normalization → Schema-locked synthesis

No triage agents. No QA agents. No agent controller framework.
LLMs are used as **structured extractors** and **constrained synthesizers** only.

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    STAGE A — Evidence Ingestion                      │
│  Connectors (ReliefWeb, UN, NGO, Gov, News) + PDF Extraction        │
│  Generator-based streaming  ·  doc_id = sha256(url)                 │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ evidence items (with PDF text)
┌──────────────────────────▼───────────────────────────────────────────┐
│                    STAGE B — Batch Enrichment                        │
│  gpt-4.1-mini  ·  strict json_schema  ·  10–20 items per call       │
│  Output: dates, geo (ISO3 + P-codes), figures, needs, risks         │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ enriched evidence
┌──────────────────────────▼───────────────────────────────────────────┐
│                    STAGE C — Ontology Normalization                  │
│  No LLM  ·  P-code/ISO normalization  ·  Figure dedup               │
│  Temporal layer  ·  Source credibility tiers                         │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ normalized ontology graph
┌──────────────────────────▼───────────────────────────────────────────┐
│                    STAGE D — SA Rendering                            │
│  Pass 1: Executive + Key Figures + Forecast (gpt-4.1, strict schema)│
│  Pass 2: 6 Sector Narratives (parallel, gpt-4.1, strict schema)     │
│  Tables: deterministic from canonical figures (never raw evidence)   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Stage A — Evidence Ingestion

### 3.1 ReliefWeb Enhancements

| Change | Detail |
|--------|--------|
| **Pagination** | Use `offset` param to iterate beyond 200 results |
| **App name** | Enforce `RELIEFWEB_APPNAME` config — fail fast if missing |
| **Format filter** | Prioritize Flash Update, Situation Report, Assessment |
| **Full fields** | Add `disaster.name`, `format.name`, `source.name`, `theme.name` |
| **Date filter** | Use `date.created` range for temporal queries |

### 3.2 Streaming Ingestion

Replace bulk retrieval with generator pattern:

```python
def stream_reliefweb_evidence(...):
    offset = 0
    while True:
        results = fetch(limit=200, offset=offset)
        if not results:
            break
        for item in results:
            yield transform(item)
        offset += 200
```

Memory-stable, early-processing, supports future concurrency without agents.

### 3.3 Stable Document Identity

```python
doc_id = sha256(url or pdf_bytes)
```

Canonical key across deduplication, entity linking, citation tracking.

### 3.4 PDF Extraction

| Layer | Engine | When |
|-------|--------|------|
| **Primary** | Docling (MIT, local) | All PDFs — headings, tables, paragraphs, layout-aware |
| **Fallback** | Tesseract | Only if Docling output is empty or low-confidence |

**Output contract:**

```python
@dataclass
class ExtractedDocument:
    text: str
    tables: list[Table]
    headings: list[str]
    page_count: int
    extraction_method: str
    confidence: float
```

This is a service layer, not an agent.

---

## 4. Stage B — Batch Enrichment

All enrichment uses `json_schema` + `strict: true`. No free-form JSON parsing anywhere.

### 4.1 Configuration

- **Model**: `gpt-4.1-mini`
- **Batch size**: 10–20 evidence items per call
- **Timeout**: 45s with 1 retry
- **Fallback**: Skip enrichment → use deterministic NLP extraction (current behavior)

### 4.2 Enrichment Output Schema

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["items"],
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["doc_id", "relevance", "published_at", "geo", "figures", "needs", "risks"],
        "properties": {
          "doc_id": { "type": "string" },
          "relevance": { "type": "number", "minimum": 0, "maximum": 1 },
          "published_at": { "type": "string" },
          "event_date": { "type": ["string", "null"] },
          "data_cutoff": { "type": ["string", "null"] },
          "temporal_confidence": { "type": "string", "enum": ["explicit", "metadata", "inferred"] },
          "geo": {
            "type": "object",
            "additionalProperties": false,
            "required": ["country_iso", "admin1_names", "admin2_names", "locations"],
            "properties": {
              "country_iso": { "type": "string" },
              "admin1_names": { "type": "array", "items": { "type": "string" } },
              "admin2_names": { "type": "array", "items": { "type": "string" } },
              "locations": { "type": "array", "items": { "type": "string" } }
            }
          },
          "figures": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["metric", "value", "unit", "scope"],
              "properties": {
                "metric": { "type": "string" },
                "value": { "type": "integer" },
                "unit": { "type": "string" },
                "scope": { "type": "string", "enum": ["admin2", "admin1", "country"] },
                "area_name": { "type": ["string", "null"] },
                "as_of": { "type": ["string", "null"] },
                "uncertainty": { "type": ["string", "null"] }
              }
            }
          },
          "needs": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["sector", "summary", "severity"],
              "properties": {
                "sector": { "type": "string", "enum": ["WASH", "Health", "Shelter", "Food", "Protection", "Education"] },
                "summary": { "type": "string" },
                "area_name": { "type": ["string", "null"] },
                "severity": { "type": "string", "enum": ["low", "medium", "high"] },
                "evidence_span": { "type": "string" }
              }
            }
          },
          "risks": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["horizon", "summary"],
              "properties": {
                "horizon": { "type": "string", "enum": ["0-7d", "7-30d", "30-90d"] },
                "summary": { "type": "string" },
                "area_name": { "type": ["string", "null"] },
                "evidence_span": { "type": "string" }
              }
            }
          }
        }
      }
    }
  }
}
```

### 4.3 Evidence Span Strategy

Store: short quote, page number (if PDF), table cell coordinates (if available).
Future-proofs citation locking without adding complexity now.

---

## 5. Stage C — Ontology Normalization

**No LLMs in this stage.** Pure deterministic logic.

### 5.1 Geo Normalization

- Internal representation: ISO3 country codes + admin names (P-codes when available)
- Country matching: **word-boundary regex** — permanently fixes Niger/Nigeria bug
- Admin matching: expanded gazetteers + LLM-extracted admin names from Stage B

### 5.2 Figure Deduplication

Cluster figures only if ALL of:
- Same `metric` (e.g. "displaced")
- Same `geo` area
- Same `scope` (admin2/admin1/country)
- Same `as_of` window (±3 days)
- Value within ±10%

**Never deduplicate across admin levels.**

Canonical value = `max(cluster_values)` with `source_count = len(cluster)`.

### 5.3 Temporal Layer

Every graph node carries:

```python
@dataclass
class TemporalAnnotation:
    published_at: str | None = None
    event_date: str | None = None
    data_cutoff: str | None = None
    validity_window: str = "current"  # "current" | "historical" | "projected"
```

SA rendering depends on this for "as of" dates and temporal ordering.

### 5.4 Expanded Gazetteers

**Phase 1 priority** (immediate need from Ethiopia SA):

| Country | Admin 1 | Admin 2 | File |
|---------|---------|---------|------|
| **Ethiopia** | 12 regions | Key zones/woredas | `config/gazetteers/ethiopia.json` |

**Phase 2 expansion** (OCHA priority countries):

| Country | Admin 1 | Status |
|---------|---------|--------|
| Somalia | 18 regions | Phase 2 |
| Sudan | 18 states | Phase 2 |
| South Sudan | 10 states | Phase 2 |
| DRC | 26 provinces | Phase 2 |
| Afghanistan | 34 provinces | Phase 2 |

Gazetteers loaded dynamically from `config/gazetteers/*.json`.

### 5.5 Source Credibility Tiers

| Tier | Sources | Weight |
|------|---------|--------|
| Tier 1 (primary) | OCHA, WFP, UNHCR, WHO, UNICEF, IOM | 1.0 |
| Tier 2 (secondary) | IFRC, MSF, Save the Children, Oxfam, IRC | 0.8 |
| Tier 3 (tertiary) | Media, government press, local news feeds | 0.5 |

Used for figure confidence scoring in deduplication.

---

## 6. Stage D — SA Rendering

### 6.1 Deterministic Tables

Tables use **only** canonical data from Stage C:

| Column Source | Example |
|---------------|---------|
| Area name | From gazetteer / enrichment geo |
| Figures | From deduplicated canonical figures |
| Severity | From enrichment severity enum |
| "As of" date | From temporal layer |
| Source | From source label |

**Rule: Never insert raw evidence description into any table cell.**

### 6.2 Two-Pass LLM Synthesis

Both passes use `gpt-4.1` with `json_schema` + `strict: true`.

**Pass 1 — Core Narrative** (single call):

```json
{
  "executive_summary": "string (max 500 words)",
  "key_figures_narrative": "string",
  "national_impact": "string",
  "access_constraints": "string",
  "forecast_risk": "string"
}
```

**Pass 2 — Sector Narratives** (6 parallel calls, one per sector):

```json
{
  "narrative": "string (max 250 words)",
  "key_messages": ["string", "string", "string"],
  "data_gaps": ["string"]
}
```

No table generation in LLM. Tables are deterministic.

### 6.3 System Prompt Standards

All SA LLM calls include:

```
OCHA WRITING STANDARDS:
- Active voice, direct statements
- Lead with impact numbers, not process descriptions
- Cite sources as [Source Name, Date]
- "As of [Date]" for all quantitative figures
- Distinguish "confirmed" vs "estimated"
- Flag data gaps explicitly — never omit silently
- IPC/CH phase language for food security
- Sphere standards for sector analysis

FACTUAL RULES:
- ONLY use provided evidence — never invent
- Report figure ranges when sources disagree
- Attribute every claim to its source
```

### 6.4 Event Name Inference (Improved)

Extended beyond named-storm regex:

| Pattern | Example Match |
|---------|---------------|
| Named storm | "Cyclone Freddy", "Typhoon Haiyan" |
| Conflict | "Ethiopia Crisis", "Sudan Conflict" |
| Epidemic | "Cholera Outbreak", "Mpox Epidemic" |
| Drought | "Horn of Africa Drought" |
| Food crisis | "Food Security Crisis" |
| Compound | "Ethiopia Multi-Hazard Crisis" |
| Fallback | "[Country] Humanitarian Situation" |

---

## 7. What We Are NOT Implementing (Yet)

| Deferred Item | Rationale | Trigger for Reconsideration |
|---------------|-----------|----------------------------|
| OCR Agent | Docling service layer is sufficient | Layout extraction quality degrades |
| Triage Agent | Batch enrichment handles classification | Relevance scoring needs per-item reasoning |
| Entity Linking Agent | Deterministic dedup handles figures | Cross-entity relationships needed |
| QA Agent | Two-pass synthesis is sufficient | Cross-sector hallucination persists |
| Agent base class | No agent orchestration needed | 3+ agent types emerge |
| Provider abstraction | OpenAI only for now | Multi-provider requirement |
| Full P-code integration (COD-AB) | Admin names sufficient for now | Cross-system interoperability needed |

---

## 8. Progress Tracker

Last updated: 2026-02-21

### Phase 1 — Foundation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | ReliefWeb pagination + appname | ✅ Done | Offset loop (10 pages × 100), appname fail-fast, date filter, extra fields (disaster/source/theme) |
| 1.2 | PDF text extraction | ✅ Done | `pdf_extract.py` — pdfplumber primary, pypdf fallback; wired into ReliefWeb connector |
| 1.3 | Fix country substring matching | ✅ Done | Word-boundary regex in `matches_country()` — Niger ≠ Nigeria |
| 1.4 | Dynamic gazetteer system | ✅ Done | `gazetteers.py` — 50+ countries, 4-layer resolution (cache→file→LLM→legacy), seed files for MDG/MOZ |
| 1.5 | Strict JSON schema on SA LLM | ✅ Done | `text.format.json_schema` on `_generate_llm_narratives()` — 11 required keys, strict mode |
| 1.6 | Rewrite deterministic tables | ✅ Done | Canonical columns (Area/Severity/Reports/Summary), no raw description dumps, HTML-cleaned summaries |
| 1.7 | Fix event name inference | ✅ Done | 3-pass: named storm → crisis pattern → type+country fallback; 12 event types mapped |
| 1.8 | Add dates + source to LLM digest | ✅ Done | `published_at`, `source_label` in digest; attribution rules in system prompt |

**Phase 1 overall**: ✅ Complete — 150/150 Python tests, 23/23 Rust tests passing

### Phase 2 — Intelligence Layer

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Temporal layer on ontology nodes | ✅ Done | `reported_date` + `source_label` on ImpactObservation, NeedStatement, RiskStatement; wired in `build_ontology_from_evidence()` |
| 2.2 | Figure deduplication | ✅ Done | MAX-per-(geo_area, figure_key) dedup in `national_figures()`, `aggregate_figures_by_admin1()`, `aggregate_figures_by_admin2()` |
| 2.3 | Batch enrichment (Stage B) | ✅ Done | `enrich_events_batch()` — 15 items/call, strict JSON schema, `_call_batch_llm()` helper, single-event fallback on failure |
| 2.4 | Geo normalization (ISO3 + gazetteers) | ✅ Done | `country_iso3` on ProcessedEvent, EventRecord, ReportEvidence, GeoArea; `country_to_iso3()` resolution in dedupe/reporting/ontology; SQLite migration |
| 2.5 | Two-pass SA synthesis | ✅ Done | Pass 1: core narrative (5 keys); Pass 2: 6 sector narratives with Pass 1 context; `_call_sa_llm()` helper extracted |
| 2.6 | "As of" dating on all figures | ✅ Done | `national_figures_with_dates()` method; "As of" + "Source" columns in impact table; inline date attribution in narratives |
| 2.7 | Streaming ingestion | ✅ Done | `fetch_stream()` generator on ReliefWeb connector — yields `RawSourceItem` page-by-page without buffering |

**Phase 2 overall**: ✅ Complete — 150/150 Python tests, 23/23 Rust tests passing

### Phase 3 — Expansion

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Citation span locking | ✅ Complete | `validate_sa_citations()`, `strip_invalid_citations()`, LLM prompt citation index |
| 3.2 | Expand gazetteers (5 countries) | ✅ Complete | SOM, SDN, SSD, COD, AFG in `config/gazetteers/` |
| 3.3 | Source credibility weighting | ✅ Complete | `source_credibility.py` — 4-tier system wired into ontology + reporting |
| 3.4 | SA quality gate | ✅ Complete | `sa_quality_gate.py` — 6-dimension scoring with configurable thresholds |
| 3.5 | Agent abstraction layer | ✅ Complete | `agents.py` — base Agent class with retry/validate/fallback + 5 concrete agents |
| 3.6 | Provider abstraction | ✅ Complete | `llm_provider.py` — LLMProvider ABC, OpenAI Responses impl, env-driven selection |

**Phase 3 overall**: ✅ Complete — 187/187 Python tests, 23/23 Rust tests passing

### Phase 4 — Deep Extraction & Pipeline Orchestration

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | PDF table extraction | ✅ Complete | `ExtractedTable`/`ExtractedDocument` dataclasses; pdfplumber table extraction with markdown conversion; backward-compat `extract_pdf_text()` wrapper |
| 4.2 | Full-article content fetching | ✅ Complete | `_fetch_page_text_with_html()` returns `(text, html)` tuple; PDF link detection from page HTML (capped at 3); RSS enclosure PDF extraction |
| 4.3 | Multi-impact per evidence | ✅ Complete | `_classify_all_impact_types()` returns ALL matching types ordered by score; one `ImpactObservation` per type; secondary types get `{}` figures to prevent double-counting |
| 4.4 | Province-level figure distribution | ✅ Complete | `distribute_national_figures()` on `HumanitarianOntologyGraph`; proportional allocation by admin1 mention counts; merges with already-localised figures; distributed flag |
| 4.5 | Coordinator pipeline upgrade | ✅ Complete | `_run_stage()` wrapper with error capture + timing; `ProgressCallback` type; `PipelineContext.stage_errors`/`stage_diagnostics`; resilient pipeline (continues on stage failure); 3-state status (ok/partial/empty) |
| 4.6 | Ontology persistence in DB | ✅ Complete | 5 new SQLModel tables (`OntologySnapshot`, `ImpactRecord`, `NeedRecord`, `RiskRecord`, `ResponseRecord`); `persist_ontology()` + `get_ontology_snapshots()` for trending; auto-migration in `init_db()` |

**Phase 4 overall**: ✅ Complete — 220/220 Python tests, 23/23 Rust tests passing

### Phase 5 — Frontend Rewrite (Project Phoenix)

**Status:** Planned (not started)  
**Timeline:** 24 weeks (6 months with 1-2 developers)  
**Scope:** Complete frontend rewrite addressing 5 critical architectural issues in current 1795-line monolithic dashboard.  
**Documentation:** [Frontend Rewrite Roadmap](frontend-rewrite-roadmap.md) | [Frontend Audit Report](../analysis/frontend-audit-report.md)

**Critical Issues Addressed:**
1. **Monolithic Architecture** → 60-80 decomposed components + feature modules
2. **State Management Chaos** → Zustand + TanStack Query + React Hook Form
3. **No Data Fetching Layer** → TanStack Query with caching + error recovery
4. **No Navigation** → React Router with tab-based layout (8 routes)
5. **Backend Bottleneck** → FastAPI + direct imports + Redis caching (10-50x faster)

**Architecture Changes:**

| Layer | Current | Target |
|-------|---------|--------|
| Language | JavaScript | TypeScript 5.x (100% strict mode) |
| Components | 2 (1795-line App.jsx) | 60-80 modular components |
| Routing | Vertical scroll | React Router 7 (8 routes) |
| State | 19 useState hooks | Zustand + TanStack Query + React Hook Form |
| UI Library | Custom CSS (649 lines) | Shadcn/ui + Tailwind |
| Backend | ThreadingHTTPServer + subprocess | FastAPI + Uvicorn + direct imports |
| Real-time | Polling | Server-Sent Events (SSE) |
| Testing | 0% coverage | 80%+ (Vitest + Testing Library) |

**10-Phase Implementation:**

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| 1. Foundation | 3 | TypeScript + Shadcn/ui + React Router + 5 routes |
| 2. Data Layer | 2 | TanStack Query + Zustand + localStorage |
| 3. Operations | 2 | `/operations` route (Command Center migration) |
| 4. Reports | 2 | `/reports` route + workbench + export |
| 5. Sources/System | 2 | `/sources` + `/system` routes |
| 6. Situation Analysis | 2 | `/sa` route + quality gate viz |
| 7. Backend Rewrite | 3 | FastAPI + Redis + JWT auth + SSE |
| 8. Real-time | 2 | SSE progress updates + notifications |
| 9. Advanced Features | 3 | Search, filters, multi-workspace |
| 10. Testing/Release | 3 | 80% coverage + performance audit + deployment |

**Success Metrics:**

| Metric | Current | Target |
|--------|---------|--------|
| API Latency | 5-30s | < 500ms (95th percentile) |
| Concurrent Users | 1-5 | 100+ |
| Component Count | 2 | 60-80 |
| Test Coverage | 0% | 80%+ |
| Lighthouse Score | 60-70 | 90+ |
| Bundle Size | 250KB | < 400KB |

**Migration Strategy:**
- Parallel deployment (`/dashboard` old, `/v2` new)
- No data migration required (SQLite + filesystem unchanged)
- Gradual cutover after Phase 10 complete
- Backward-compatible API shim during transition

---

## 9. Implementation Phases

### Phase 1 — Foundation (3–4 days)

**Goal**: Fix every defect visible in the Ethiopia SA output.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 1.1 | Add ReliefWeb pagination + `appname` enforcement | Fetches > 200 results; fails fast without appname |
| 1.2 | Integrate Docling OCR for PDF extraction | Flash Update PDFs return structured text + tables |
| 1.3 | Fix country substring matching (word-boundary) | "Niger" does NOT match "Nigeria" |
| 1.4 | Add Ethiopia gazetteer (`config/gazetteers/ethiopia.json`) | Ethiopia admin1/admin2 tables populated |
| 1.5 | Add strict JSON schema to SA LLM calls | All SA LLM responses validate against schema |
| 1.6 | Rewrite deterministic tables (no raw evidence) | Sector tables show canonical figures + severity + source |
| 1.7 | Fix event name inference (conflict, epidemic, drought) | Ethiopia SA shows "Ethiopia [Type] Crisis" not "Unknown Event" |
| 1.8 | Add `published_at` + `source_label` to LLM evidence digest | LLM receives dates and source attribution |

**Success milestone**: Ethiopia SA output has zero garbage text, populated admin tables, correct event name, dated figures.

### Phase 2 — Intelligence Layer (4–6 days)

**Goal**: Structured enrichment pipeline with deduplication and temporal awareness.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 2.1 | Add temporal layer to all ontology nodes | Every `ImpactObservation`, `NeedStatement`, `RiskStatement` carries dates |
| 2.2 | Implement figure deduplication | Same figure from 2 sources → 1 canonical figure (not doubled) |
| 2.3 | Implement batch enrichment with strict schema (Stage B) | 10–20 items per call, `gpt-4.1-mini`, strict JSON output |
| 2.4 | Implement geo normalization (ISO3 + expanded gazetteers) | Country matching uses word-boundary; admin names from enrichment |
| 2.5 | Enable two-pass SA synthesis (Stage D) | Pass 1: core narrative; Pass 2: 6 sector narratives in parallel |
| 2.6 | Add "as of" dating to all SA figures and sections | Every number in SA output shows date attribution |
| 2.7 | Streaming ingestion (generator pattern) | ReliefWeb connector yields items instead of bulk list |

**Success milestone**: SA figures are deduplicated and dated. Sector narratives are synthesized (not raw evidence). LLM costs ~$0.05–0.12 per SA.

### Phase 3 — Expansion (when needed)

**Goal**: Scale to more countries and add deeper quality controls. Only triggered when Phase 2 is stable.

| # | Task | Trigger |
|---|------|---------|
| 3.1 | Citation span locking | When claim attribution needs enforcement |
| 3.2 | Expand gazetteers (Somalia, Sudan, South Sudan, DRC, Afghanistan) | When SA is requested for these countries |
| 3.3 | Source credibility tier weighting | When figure confidence scoring shows noise |
| 3.4 | SA quality gate (automated scoring) | When SA volume warrants automated QA |
| 3.5 | Agent abstraction layer | When 3+ distinct agent types are needed |
| 3.6 | Provider abstraction (multi-LLM) | When non-OpenAI models are needed |

---

## 10. Cost & Latency Profile

| Architecture | Cost per SA | Latency | Complexity | Quality |
|-------------|------------|---------|-----------|---------|
| Current | ~$0.01 | Low | Low | Poor (garbage text) |
| **Reduced++** | **~$0.05–0.12** | **Moderate** | **Moderate** | **Good** |
| Full Multi-Agent | ~$0.50 | High | High | Best (deferred) |

Reduced++ delivers the **quality jump** at 10× lower cost and complexity than full multi-agent.

---

## 11. Architectural Principle

> This system must behave as a **deterministic humanitarian intelligence engine**
> using LLMs as **structured extractors** and **constrained synthesizers**.
>
> The fewer uncontrolled generative steps, the more stable the output.

---

## References

| Document | Purpose |
|----------|---------|
| [SA Quality Analysis](../analysis/sa-improvement-analysis.md) | Root cause analysis of all SA defects |
| [MVP Roadmap (archived)](archive/mvp-roadmap.md) | Previous phase — all milestones closed |
| [Frontend Roadmap (archived)](archive/frontend-roadmap.md) | Previous phase — baseline through SA UI |
| [LLM Intelligence Layer v1](../../specs/15-llm-intelligence-layer-v1.md) | Spec for enrichment + ontology |
| [System Architecture](../../specs/06-architecture.md) | Module-level architecture |

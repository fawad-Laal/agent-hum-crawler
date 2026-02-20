# System Architecture — Dynamic Disaster Intelligence Assistant

Date: 2026-02-20
Version: 1.0

## 1. Overview

The Dynamic Disaster Intelligence Assistant (agent-hum-crawler) is a Python-based humanitarian monitoring pipeline that continuously collects, normalises, deduplicates, and analyses disaster event data from diverse online sources. It produces structured alerts, long-form intelligence reports, and OCHA-style Situation Analysis documents for humanitarian decision-makers.

The system is designed as a modular pipeline with six principal layers:

```
┌────────────────────────────────────────────────────────────────────┐
│                    Operator / Frontend Layer                       │
│  React Dashboard (ui/)  ←→  Dashboard API (scripts/dashboard_api) │
└───────────────────────────────┬────────────────────────────────────┘
                                │ HTTP / subprocess
┌───────────────────────────────▼────────────────────────────────────┐
│                        CLI Entrypoint                              │
│                   src/agent_hum_crawler/main.py                    │
│  Commands: run-cycle, write-report, write-situation-analysis,      │
│            quality-report, source-health, hardening-gate, ...      │
└──┬──────────┬──────────┬───────────┬──────────┬───────────────────┘
   │          │          │           │          │
   ▼          ▼          ▼           ▼          ▼
┌──────┐ ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────────┐
│Intake│ │Collect │ │Intel   │ │Report   │ │Situation     │
│Layer │ │Layer   │ │Layer   │ │Layer    │ │Analysis Layer│
└──┬───┘ └──┬─────┘ └──┬─────┘ └──┬──────┘ └──┬───────────┘
   │        │          │           │           │
   ▼        ▼          ▼           ▼           ▼
┌────────────────────────────────────────────────────────────────────┐
│                     Persistence Layer (SQLite)                     │
│              ~/.moltis/agent-hum-crawler/monitoring.db             │
└────────────────────────────────────────────────────────────────────┘
```

## 2. Module Map

### 2.1 Core Pipeline Modules (`src/agent_hum_crawler/`)

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| `main.py` | CLI entrypoint, argument parsing, command dispatch | `build_parser()`, `main()` |
| `config.py` | Runtime config schema, disaster type normalisation | `RuntimeConfig`, `canonicalize_disaster_type()` |
| `intake.py` | Config intake and validation from user input | Config loading |
| `cycle.py` | Monitoring cycle orchestration | `run_cycle()` |
| `database.py` | SQLModel persistence (SQLite) | `EventRecord`, `RawItemRecord`, `CycleRecord`, `build_engine()` |
| `dedupe.py` | Fuzzy deduplication, change detection, severity/confidence scoring | Dedupe pipeline |
| `models.py` | Shared data models and enums | Event model types |
| `state.py` | Cycle state tracking (hashes, timestamps) | State persistence |
| `taxonomy.py` | Disaster type taxonomy and classification | Type mappings |
| `time_utils.py` | Date/time parsing utilities | `parse_published_datetime()` |
| `url_canonical.py` | URL canonicalisation for citation deduplication | `canonical_url()` |
| `settings.py` | Environment/secrets loading (.env, API keys) | `get_openai_api_key()`, `get_openai_model()` |
| `feature_flags.py` | Centralised runtime feature toggle system | Flag loading and evaluation |

### 2.2 Source Collection Modules

| Module | Purpose |
|--------|---------|
| `connectors/` | Source connector implementations (ReliefWeb API, GDACS, FEWS NET, RSS feeds) |
| `source_registry.py` | Source registry and feed URL management |
| `source_freshness.py` | Per-source freshness tracking, stale detection, and demote policies |

### 2.3 Intelligence & Analysis Modules

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| `llm_enrichment.py` | Optional LLM-based severity/confidence calibration and summarisation | LLM enrichment pipeline |
| `graph_ontology.py` | Humanitarian ontology graph — typed nodes for hazards, impacts, needs, responses, risks, admin areas | `HumanitarianOntologyGraph`, `build_ontology_from_evidence()`, `_extract_figures()` |
| `reporting.py` | GraphRAG evidence retrieval, long-form report rendering, citation management | `build_graph_context()`, `render_long_form_report()`, `write_report()` |
| `situation_analysis.py` | OCHA-style Situation Analysis renderer (15 sections) | `render_situation_analysis()`, `write_situation_analysis()` |

### 2.4 Quality & Hardening Modules

| Module | Purpose |
|--------|---------|
| `hardening.py` | Hardening gate thresholds and pass/fail evaluation |
| `conformance.py` | Conformance report combining hardening + Moltis integration checks |
| `alerts.py` | Alert emission rules and severity-based filtering |
| `hook_policies.py` | Moltis hook safety policy enforcement |
| `pilot.py` | Multi-cycle pilot orchestration |
| `replay.py` | Deterministic replay from fixtures for testing |

### 2.5 Operator Interface

| Component | Path | Purpose |
|-----------|------|---------|
| Dashboard API | `scripts/dashboard_api.py` | Python stdlib ThreadingHTTPServer bridging React UI to CLI commands |
| React Dashboard | `ui/src/App.jsx` | Single-page operator console (Vite + React) |
| E2E Gate | `scripts/e2e_gate.py` | Deterministic end-to-end regression gate with artifact capture |
| Security Check | `scripts/moltis_security_check.py` | Automated Moltis auth/security baseline verifier |
| Local Validate | `scripts/local-validate.ps1`, `scripts/local-validate.sh` | Pre-commit validation gate |

## 3. Data Flow

### 3.1 Monitoring Cycle

```
[Source Connectors]     → Fetch RSS/API data
        ↓
[Normalisation]         → Parse into EventRecord candidates
        ↓
[Dedupe / Change Detect]→ Hash + fuzzy match against prior cycles
        ↓
[Severity / Confidence] → Rule-based scoring (+ optional LLM calibration)
        ↓
[Persistence]           → Write EventRecord + RawItemRecord to SQLite
        ↓
[Alert Emission]        → Format and deliver high-severity alerts
```

### 3.2 Report Generation

```
[SQLite Evidence]       → Query EventRecord + RawItemRecord by filters
        ↓
[build_graph_context()] → Score and rank evidence by graph facets
        ↓                  (country, disaster_type, connector, corroboration)
[Evidence Selection]    → Balanced selection with per-source/connector caps
        ↓
[Report Rendering]      → Template-driven markdown with deterministic tables
        ↓                  (+ optional LLM narrative drafting)
[Quality Gates]         → Citation density, section completeness, claim checks
        ↓
[Output]                → Markdown file in reports/ directory
```

### 3.3 Situation Analysis

```
[build_graph_context()] → Retrieve scored evidence from SQLite
        ↓
[build_ontology_from_  → Construct HumanitarianOntologyGraph:
 evidence()]              - Extract figures (deaths, displaced, affected, etc.)
        ↓                 - Classify hazards, impacts, needs, responses, risks
                          - Detect admin areas from text vs gazetteer
                          - Auto-load country gazetteer (admin1 → admin2)
[Auto-inference]        → Detect event name ("Cyclone Gezani") and type
        ↓                  from evidence titles/text
[render_situation_     → Render 15-section OCHA-style report:
 analysis()]              1. Executive Summary (event card + key figures)
        ↓                 2. National Impact Table
                          3-4. Admin 1/2 Impact Tables
                          5-10. Sectoral Analyses (Shelter, WASH, Health, 
                                Food Security, Protection, Education)
                          11. Access Constraints (keyword-extracted)
                          12. Outstanding Needs & Gaps
                          13. Forecast & Risk Outlook
                          14. Admin Reference Annex (from gazetteer)
                          15. Citations
[Output]                → Markdown file + API JSON response
```

## 4. Humanitarian Ontology Graph

The `HumanitarianOntologyGraph` is the core analytical data structure for structured evidence retrieval.

### 4.1 Node Types

```
HumanitarianOntologyGraph
├── hazards: dict[str, HazardNode]
│   ├── name, category (geophysical/hydrological/meteorological/...)
│   └── impact_ids, need_ids, risk_ids (links to child nodes)
│
├── impacts: list[ImpactObservation]
│   ├── description, impact_type (PEOPLE/HOUSING/INFRASTRUCTURE/...)
│   ├── figures: dict[str, int] (deaths, displaced, houses_affected, ...)
│   ├── severity (1-5 phase scale)
│   └── admin_area, source_url
│
├── needs: list[NeedStatement]
│   ├── need_type (SHELTER/WASH/HEALTH/FOOD_SECURITY/PROTECTION/EDUCATION/LOGISTICS)
│   ├── description, severity
│   └── admin_area
│
├── responses: list[ResponseAction]
│   ├── actor, actor_type (un_agency/ngo/government/...)
│   └── description
│
├── risks: list[RiskStatement]
│   ├── description, hazard_name
│   ├── horizon (48h/7d/30d)
│   └── likelihood, impact
│
└── admin_areas: dict[str, AdminArea]
    ├── name, level (admin1/admin2)
    ├── parent (admin1 name for admin2 areas)
    └── impact_ids, need_ids (links to observations)
```

### 4.2 Figure Extraction Pipeline

Four complementary regex patterns extract numeric figures from evidence text:

| Pattern | Example | Captures |
|---------|---------|----------|
| Standard `NUM keyword` | "48,000 displaced" | displaced: 48000 |
| Death toll verbs | "death toll rises to 59" | deaths: 59 |
| Quantifier prefix | "at least 52 dead" | deaths: 52 |
| Sentence-level | "59 killed in the storm" | deaths: 59 |

Figures use `max()` accumulation to prevent double-counting when the same number matches multiple patterns.

### 4.3 Country Gazetteers

Built-in admin hierarchies for geo-detection:

| Country | Admin 1 (Provinces) | Admin 2 (Districts) |
|---------|--------------------|--------------------|
| Madagascar | 22 provinces | 100+ districts |
| Mozambique | 10 provinces | 50+ districts |

The system auto-detects countries from evidence and loads matching gazetteers when no explicit hierarchy is provided.

## 5. Persistence Model

SQLite database at `~/.moltis/agent-hum-crawler/monitoring.db`.

### 5.1 Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `cyclerecord` | Monitoring cycle metadata | id, started_at, events_count, connector states |
| `eventrecord` | Normalised disaster events | event_id, country, disaster_type, severity, confidence, title, summary, url, published_at, llm_enriched, corroboration_sources |
| `rawitemrecord` | Raw source payloads | cycle_id, url, payload_json (contains `text` field), connector |

### 5.2 Evidence Quality Fields

- `corroboration_sources`: count of independent sources confirming the event.
- `severity`: 1-5 integer scale (low to critical).
- `confidence`: 1-5 integer scale (speculative to verified).
- `llm_enriched`: boolean flag for LLM-processed events.
- `citations_json`: serialised citation metadata.

## 6. Dashboard API Architecture

The dashboard API (`scripts/dashboard_api.py`) is a Python stdlib `ThreadingHTTPServer` that wraps CLI commands via subprocess.

### 6.1 Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/overview` | System status, cycle history, feature flags |
| POST | `/api/run-cycle` | Trigger monitoring cycle |
| POST | `/api/write-report` | Generate long-form report |
| POST | `/api/write-situation-analysis` | Generate OCHA Situation Analysis |
| POST | `/api/report-workbench` | Side-by-side deterministic vs AI report compare |
| POST | `/api/source-check` | Per-source feed diagnostic |
| GET | `/api/reports` | List generated reports |
| GET | `/api/report/<name>` | Fetch specific report markdown |
| GET/POST | `/api/workbench-profiles/*` | Save/load/delete compare presets |

### 6.2 Frontend Architecture

Single-page React application (`ui/src/App.jsx`) built with Vite:

- Operator controls: country/disaster filters, template selection, LLM toggle, retrieval tuning knobs.
- KPI dashboard: trend charts, hardening thresholds, conformance/security status.
- Report workbench: side-by-side compare, quality diagnostics, section budget table.
- SA generation: collapsible parameter form, one-click generation, markdown output display.
- Source diagnostics: per-source health table with freshness badges and match-reason diagnostics.

## 7. Configuration Files

| File | Purpose |
|------|---------|
| `config/country_sources.json` | Country-specific source feed URLs |
| `config/feature_flags.json` | Runtime feature toggles |
| `config/report_template.json` | Default report template |
| `config/report_template.brief.json` | Brief donor update template |
| `config/report_template.detailed.json` | Detailed analyst brief template |
| `config/report_template.situation_analysis.json` | OCHA SA template (15 sections) |
| `config/moltis.hardened.example.toml` | Hardened Moltis profile template |

## 8. Testing Architecture

114 tests across 17 test files:

| Test File | Coverage Area |
|-----------|---------------|
| `test_alerts.py` | Alert emission rules |
| `test_config_validation.py` | Runtime config schema |
| `test_conformance.py` | Conformance report generation |
| `test_database.py` | SQLite persistence operations |
| `test_dedupe.py` | Deduplication and change detection |
| `test_feature_flags.py` | Feature flag evaluation |
| `test_feed_hardening.py` | Feed parsing robustness |
| `test_hardening.py` | Hardening gate thresholds |
| `test_hook_policies.py` | Hook safety policy enforcement |
| `test_llm_enrichment.py` | LLM enrichment pipeline |
| `test_moltis_security_check.py` | Security baseline validation |
| `test_pilot.py` | Pilot orchestration |
| `test_reliefweb_connector.py` | ReliefWeb API connector |
| `test_replay.py` | Deterministic replay |
| `test_reporting.py` | Report generation and quality gates |
| `test_situation_analysis.py` | SA rendering (20 tests) |
| `test_graph_ontology.py` | Ontology graph, figure extraction, classification (34 tests) |

## 9. Quality Gates

### 9.1 Report Quality Gates
- Citation density threshold (`min_citation_density`).
- Section completeness (all required sections present).
- Unsupported-claim detection (incident blocks without source URLs).
- Invalid citation reference detection.

### 9.2 Hardening Gates
- Duplicate rate estimate below threshold.
- Traceable rate above threshold.
- LLM enrichment rate within expected range.
- Source health metrics within tolerance.

### 9.3 E2E Regression Gate
Deterministic end-to-end gate (`scripts/e2e_gate.py`) runs:
1. Replay from fixtures
2. Report generation with quality enforcement
3. Hardening gate evaluation
4. Conformance report
5. Security baseline check
6. Artifacts captured to `artifacts/e2e/<UTC timestamp>/`

## 10. Deployment Model

### 10.1 Local Development
- Python 3.12, installed editable (`pip install -e .`)
- SQLite database in user home directory
- Dashboard API on `127.0.0.1:8788`
- React dev server on `localhost:5174` (Vite)

### 10.2 Moltis Integration
- Agent runs as a Moltis skill with hook-based safety controls.
- Config stored in `~/.config/moltis/moltis.toml`.
- Hook registry: `~/.moltis/hooks/` (audit, LLM guard, tool safety guard).
- Session branching for incident-specific analysis forks.

## 11. Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| DB | SQLite via SQLModel |
| Validation | Pydantic v2 |
| HTTP Client | httpx |
| LLM | OpenAI Responses API (optional) |
| Frontend | React + Vite |
| Testing | pytest |
| Package | pyproject.toml (editable install) |

## 12. Security Posture

- No autonomous external actions without source attribution.
- Sandboxed browser execution when used.
- Scoped API keys with least-privilege enforcement.
- Hook-based safety controls (destructive command blocking, injection detection).
- Audit logging to `~/.moltis/logs/hook-audit.jsonl`.
- Auth-enabled Moltis config required for non-local deployments.
- Automated security baseline validation in E2E gate.

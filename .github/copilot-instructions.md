# GitHub Copilot Instructions — Personal-Assistant-Moltis (Project Moltis)

> These instructions are loaded automatically for every Copilot request in this workspace.
> Detailed project memory is available in `.projectmemory/` — read those files for deep context.

---

## Project Overview

**Moltis** is a humanitarian disaster intelligence platform:
- **Backend** (`src/agent_hum_crawler/`): Python, SQLModel, SQLite (`src/agent_hum_crawler/crawler.db`)
- **Frontend** (`ui-phoenix/`): TypeScript, React 19, Vite 7, TanStack Query v5, Zustand, Zod, Tailwind CSS v4.2, Recharts
- **Rust core** (`rust_core/`): PyO3 extension — NLP utilities (figure extraction, fuzzy dedup, text classify)
- **Dashboard API** (`scripts/dashboard_api.py`): HTTP server on port 8788, calls backend CLI via `subprocess`
- **Tests**: Frontend — Vitest + Testing Library; Backend — pytest

---

## Architecture (key modules)

See `.projectmemory/context/architecture_summary.txt` for the full module map and dependency graph.

| Module | Role |
|--------|------|
| `src/agent_hum_crawler/models.py` | SQLModel ORM — `ContentSource`, `RawSourceItem`, `FetchResult`, `ProcessedEvent`, `EventCitation` |
| `src/agent_hum_crawler/coordinator.py` | Orchestrates collection → enrichment → report pipeline |
| `src/agent_hum_crawler/cycle.py` | Single evidence-collection cycle; source health check |
| `src/agent_hum_crawler/situation_analysis.py` | Generates OCHA-style SA from `ProcessedEvent` rows |
| `src/agent_hum_crawler/graph_ontology.py` | Event ontology & deduplication graph |
| `src/agent_hum_crawler/llm_provider.py` | LLM abstraction (OpenAI/Ollama/stub) |
| `ui-phoenix/src/lib/api.ts` | All HTTP calls to dashboard API |
| `ui-phoenix/src/hooks/use-mutations.ts` | TanStack Query mutation hooks (toast at hook level, survives navigation) |
| `ui-phoenix/src/lib/schemas.ts` | Zod schemas for all API responses |
| `ui-phoenix/src/types/index.ts` | TypeScript interfaces for all data shapes |

---

## Database

**ORM**: SQLModel (NOT Django — the `.projectmemory/database.schema.json` may label it Django incorrectly).  
**File**: `src/agent_hum_crawler/crawler.db` (SQLite)  
**Key tables**: `content_source`, `raw_source_item`, `fetch_result`, `processed_event`, `event_citation`

See `.projectmemory/database_summary.txt` for the table summary.

---

## Frontend Architecture

```
ui-phoenix/src/
  lib/
    api.ts          — fetch functions (RunCycleParams, WriteSAParams, etc.)
    schemas.ts      — Zod validation schemas (saQualityGateSchema, saResponseSchema, etc.)
    query-client.ts — TanStack Query client
  hooks/
    use-mutations.ts  — 5 mutations: useRunCycle, useWriteReport, useRunSourceCheck, useWriteSA, useRunPipeline
    use-queries.ts    — query hooks for GET endpoints
  stores/
    form-store.ts     — Zustand persisted form state (CollectionForm)
  features/
    operations/       — Command Center page (all workflow forms)
    situation-analysis/ — SA page (Phase 6)
    reports/          — Report browser + workbench
    sources/          — Source intelligence page
    system/           — System info page
    settings/         — Feature flags + settings
  components/
    charts/           — Recharts chart components (CycleQualityChart, SAQualityGateChart)
    ui/               — shadcn/ui primitives
```

### SA Quality Gate shape (backend response)
```typescript
interface SAQualityGate {
  overall_score?: number;      // 0-1 float
  passed?: boolean;
  section_completeness?: number;
  key_figure_coverage?: number;
  citation_accuracy?: number;
  citation_density?: number;
  admin_coverage?: number;
  date_attribution?: number;
  details?: unknown;           // object (variable shape) — NOT array
}
```

---

## Key Variables & Interfaces

See `.projectmemory/variables_summary.txt` for the full exported symbols list.

Frequently used:
- `CollectionForm` — Zustand form store shape (see `ui-phoenix/src/types/index.ts`)
- `WriteSAParams` — `{ countries, disaster_types, title, event_name, event_type, period, sa_template, limit_cycles, limit_events, max_age_days, use_llm, quality_gate }`
- `RunCycleParams` — `{ countries, disaster_types, limit, max_age_days }`
- `SAResponse` — `{ markdown, output_file?, quality_gate?, status? }`

---

## CLI Commands

```bash
# Collect data
agent-hum-crawler run-cycle --countries Lebanon --disaster-types conflict

# Generate SA
agent-hum-crawler write-situation-analysis --countries Lebanon --disaster-types conflict \
  --event-name "Lebanon Conflict" --use-llm --quality-gate

# Run full pipeline
agent-hum-crawler run-pipeline --countries Lebanon --disaster-types conflict --use-llm

# Source health check
agent-hum-crawler run-source-check --countries Lebanon
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `config/country_sources.json` | RSS/HTTP feeds per country (Lebanon, Pakistan, Bangladesh, Madagascar, Mozambique, Ethiopia configured) |
| `config/feature_flags.json` | Toggle flags for LLM use, strict filters, etc. |
| `config/report_template.situation_analysis.json` | OCHA SA template structure |
| `config/moltis.hardened.example.toml` | Hardened runtime security config |

---

## Test Suite (Frontend)

Located in `ui-phoenix/tests/unit/`. Run with `npx vitest run` from `ui-phoenix/`.

| File | Phase | Tests |
|------|-------|-------|
| `utils.test.ts` | 1 | 18 |
| `schemas.test.ts` | 2 | 26 |
| `form-store.test.ts` | 3 | 8 |
| `routes.test.tsx` | 3 | 7 |
| `reports-phase4.test.tsx` | 4 | 18 |
| `phase5.test.tsx` | 5 | 26 |
| `phase6.test.tsx` | 6 | 22 |

**Current status**: 7/7 files, 125 tests passing, 0 TypeScript errors.

---

## Important Patterns

### Mutation toasts survive navigation
All 5 mutations in `use-mutations.ts` emit toasts at **hook level** (not component-level per-mutate callbacks), so they fire even if the user navigates away before the task completes. Component-level callbacks are only used for local UI state.

### Zod schema validation
All API responses are validated through Zod schemas in `schemas.ts`. Use `.passthrough()` on object schemas to allow extra fields. The `details` field in `saQualityGateSchema` is `z.unknown()` because the backend can return either an object or an array.

### Country sources format
`country_sources.json` has `{ "global": [...], "countries": { "Lebanon": [...], ... } }` where each source entry has `url`, `connector_type`, `label`, etc.

# Moltis â€” Humanitarian Disaster Intelligence Platform

**Moltis** is an operator-grade humanitarian disaster intelligence system that collects multi-source evidence, enriches it with an AI/LLM pipeline, and generates OCHA-style Situation Analyses and GraphRAG reports â€” all from a modern React dashboard or the CLI.

> **Project Phoenix phases 1â€“6 complete** â€” 125 frontend tests, 0 TypeScript errors.  
> **Phase 7 (FastAPI backend)** — direct-import migration complete; optional Redis job caching added.

---

## Architecture

| Layer | Technology |
|---|---|
| CLI / backend | Python 3.11+, SQLModel, SQLite (`crawler.db`) |
| Dashboard API | `scripts/dashboard_api.py` (HTTP bridge) â†’ **`src/agent_hum_crawler/api/`** (FastAPI, in migration) |
| Frontend | `ui-phoenix/` â€” TypeScript, React 19, Vite 7, TanStack Query v5, Zustand, Tailwind CSS v4.2, Recharts |
| NLP core | `rust_core/` â€” PyO3 extension (figure extraction, fuzzy dedup, text classify) |
| Tests | Backend: pytest (220+ passing) Â· Frontend: Vitest + Testing Library (125 passing) |

---

## Quick Start

### 1 â€” Install

```powershell
python -m pip install -e .[dev]
```

Requires Python â‰¥ 3.11. Key runtime dependencies (auto-installed):

- `fastapi`, `uvicorn[standard]` â€” dashboard API server
- `sqlmodel` â€” ORM + SQLite persistence
- `httpx`, `feedparser`, `trafilatura`, `beautifulsoup4` â€” feed ingestion
- `pdfplumber`, `pypdf` â€” PDF extraction
- `APScheduler` â€” scheduled cycles

### 2 â€” Configure

```powershell
# Copy and fill in your keys
cp config/country_sources.example.json config/country_sources.json
cp config/feature_flags.example.json config/feature_flags.json
```

Create `.env` in the project root:

```env
RELIEFWEB_ENABLED=true
RELIEFWEB_APPNAME=your_approved_reliefweb_appname
LLM_ENRICHMENT_ENABLED=false
OPENAI_API_KEY=sk-...          # only needed when LLM_ENRICHMENT_ENABLED=true
OPENAI_MODEL=gpt-4.1-mini
```

### 3 â€” Start the dashboard

```powershell
# Terminal 1 â€” API bridge (port 8788)
python scripts/dashboard_api.py --host 127.0.0.1 --port 8788

# Terminal 2 â€” React frontend (port 5175)
cd ui-phoenix
npm install
npm run dev
```

Open `http://localhost:5175` â€” the Phoenix dashboard.

> **FastAPI docs** (Phase 7 backend): `http://localhost:8788/api/docs`

---

## Dashboard Features (Project Phoenix)

| Page | Route | Description |
|---|---|---|
| Overview | `/` | KPI cards, cycle trends, source health summary, credibility distribution |
| Operations | `/operations` | Run cycles, write reports, source checks, full pipeline â€” all with form controls |
| Reports | `/reports` | Virtualized report list, markdown viewer, HTML/JSON export, workbench compare |
| Situation Analysis | `/sa` | OCHA-style SA generation with quality gate scores and 6-dimension chart |
| Sources | `/sources` | Source health table, connector diagnostics, freshness trend chart |
| System | `/system` | Feature flags panel, E2E gate summary, security baseline card |
| Data | `/data` | **Database explorer** â€” browse Cycle Runs, Events, Raw Items, Feed Health live |
| Settings | `/settings` | Feature toggles |

---

## CLI Commands

### Evidence Collection

```powershell
# Single monitoring cycle â€” fetch, enrich, persist
agent-hum-crawler run-cycle --countries Lebanon --disaster-types conflict

# With recency and content extraction
agent-hum-crawler run-cycle \
  --countries "Pakistan,Bangladesh" \
  --disaster-types "flood,cyclone/storm" \
  --limit 15 --max-age-days 30 --include-content
```

### Situation Analysis

```powershell
# Generate OCHA-style SA (deterministic)
agent-hum-crawler write-situation-analysis \
  --countries Lebanon --disaster-types conflict \
  --event-name "Lebanon Conflict" --period "Q1 2026"

# With LLM narrative + quality gate enforcement
agent-hum-crawler write-situation-analysis \
  --countries Lebanon --disaster-types conflict \
  --event-name "Lebanon Conflict" --use-llm --quality-gate
```

### Report Generation

```powershell
# Brief donor update
agent-hum-crawler write-report \
  --countries Madagascar --disaster-types "cyclone/storm" \
  --report-template config/report_template.brief.json --use-llm

# Detailed analyst brief with retrieval balancing
agent-hum-crawler write-report \
  --countries "Madagascar,Mozambique" --disaster-types "cyclone/storm,flood" \
  --limit-cycles 25 --limit-events 20 --use-llm \
  --country-min-events 1 --max-per-connector 8 --max-per-source 4 \
  --report-template config/report_template.detailed.json
```

### KPI & Quality

```powershell
agent-hum-crawler quality-report --limit 10
agent-hum-crawler source-health --limit 10
agent-hum-crawler hardening-gate --limit 10
agent-hum-crawler llm-report --limit 10 \
  --min-llm-enrichment-rate 0.10 --min-citation-coverage-rate 0.95
```

### Source Diagnostics

```powershell
# One-by-one feed connectivity check (read-only)
agent-hum-crawler source-check \
  --countries Lebanon --disaster-types conflict --max-age-days 30
```

### Pipeline

```powershell
# Full collect â†’ enrich â†’ SA pipeline
agent-hum-crawler run-pipeline \
  --countries Lebanon --disaster-types conflict --use-llm
```

### Pilot & Replay

```powershell
# Automated 7-cycle evidence pack
agent-hum-crawler pilot-run \
  --countries "Madagascar,Mozambique" \
  --disaster-types "cyclone/storm,flood" \
  --cycles 7 --limit 10 --include-content --reset-state-before-run

# Dry-run replay fixture
agent-hum-crawler replay-fixture \
  --fixture tests/fixtures/replay_pakistan_flood_quake.json
```

### Scheduled Monitoring

```powershell
agent-hum-crawler start-scheduler \
  --countries Pakistan --disaster-types "flood,earthquake" \
  --interval 30 --limit 10 --max-runs 1
```

---

## Configuration

### Country Sources (`config/country_sources.json`)

```json
{
  "global": [ { "url": "...", "connector_type": "rss", "label": "BBC World" } ],
  "countries": {
    "Lebanon": [ { "url": "...", "connector_type": "rss", "label": "..." } ]
  }
}
```

Active countries: Madagascar, Mozambique, Pakistan, Bangladesh, Ethiopia, Lebanon.

Global feeds include: BBC World, Al Jazeera, AllAfrica, Africanews, ANA, Guardian, Reuters, NYT World, NPR World.

Government/humanitarian sources include USGS Earthquakes, GDACS (all/floods/cyclones 7d), CARE, FEWS NET.

### Feature Flags (`config/feature_flags.json`)

Centralized runtime toggles. Override via environment:

```
AHC_FLAG_LLM_ENRICHMENT_ENABLED=true
```

Key flags: `reliefweb_enabled`, `llm_enrichment_enabled`, `report_strict_filters_default`, `stale_feed_auto_warn_enabled`, `stale_feed_auto_demote_enabled`.

### Report Templates

| File | Use |
|---|---|
| `config/report_template.json` | Default balanced report |
| `config/report_template.brief.json` | Short donor update |
| `config/report_template.detailed.json` | Long analyst brief |
| `config/report_template.situation_analysis.json` | OCHA SA 15-section template |

---

## Tests

```powershell
# Backend (pytest)
pytest -q

# Frontend (Vitest)
cd ui-phoenix
npx vitest run

# Local validation gate (pytest + compileall + E2E)
.\scripts\local-validate.ps1          # Windows
./scripts/local-validate.sh           # Linux/macOS

# Skip E2E pass
.\scripts\local-validate.ps1 -SkipE2E
```

**Frontend test suite** (`ui-phoenix/tests/unit/`):

| File | Phase | Tests |
|---|---|---|
| `utils.test.ts` | 1 | 18 |
| `schemas.test.ts` | 2 | 26 |
| `form-store.test.ts` | 3 | 8 |
| `routes.test.tsx` | 3 | 7 |
| `reports-phase4.test.tsx` | 4 | 18 |
| `phase5.test.tsx` | 5 | 26 |
| `phase6.test.tsx` | 6 | 22 |
| **Total** | | **125** |

E2E artifacts written to `artifacts/e2e/<UTC timestamp>/`.

---

## Backend API (Phase 7 â€” FastAPI)

The new API module lives at `src/agent_hum_crawler/api/` and is being migrated from subprocess CLI calls to direct Python imports.

**App factory**: `agent_hum_crawler.api.app:create_app()`

Route modules under `src/agent_hum_crawler/api/routes/`:

| Module | Endpoints |
|---|---|
| `health` | `GET /api/health` |
| `overview` | `GET /api/overview`, `GET /api/system-info` |
| `cycle` | `POST /api/run-cycle`, `POST /api/source-check` |
| `reports` | `GET /api/reports`, `GET /api/report-content` |
| `situation_analysis` | `POST /api/write-situation-analysis` |
| `workbench` | `POST /api/report-workbench` |
| `db` | `GET /api/db/cycles`, `GET /api/db/events`, `GET /api/db/raw-items`, `GET /api/db/feed-health` |
| `settings` | `GET /api/feature-flags`, `POST /api/update-feature-flag` |
| `jobs` | `GET /api/jobs/{id}` (async job status) |

Interactive docs: `http://localhost:8788/api/docs`

---

## Ontology & SA Engine

Built in `src/agent_hum_crawler/graph_ontology.py` and `situation_analysis.py`:

- **`HumanitarianOntologyGraph`** â€” typed nodes: `HazardNode`, `ImpactObservation`, `NeedStatement`, `ResponseAction`, `RiskStatement`, `AdminArea`
- **Multi-pattern NLP figure extraction** â€” 4 regex patterns with `max()` accumulation to prevent double-counting
- **Country gazetteers** â€” 50+ countries with admin1/admin2 hierarchies (`config/gazetteers/`)
- **SA quality gate** â€” 6-dimension scoring: section completeness, key figure coverage, citation accuracy/density, admin coverage, date attribution
- **Two-pass LLM synthesis** â€” Pass 1: core narrative; Pass 2: 6 sector narratives with shared context
- **Source credibility weighting** â€” 4-tier system: UN/OCHA â†’ NGO/Gov â†’ Major News â†’ Other

---

## Security & Ops

### Moltis Hook Pack

Project-local hooks under `.moltis/hooks/`:
- `llm-tool-guard` â€” `BeforeLLMCall`, `AfterLLMCall`
- `tool-safety-guard` â€” `BeforeToolCall`
- `audit-log` â€” `Command`, `MessageSent`, `AfterToolCall`, `BeforeToolCall`, `AfterLLMCall`

```powershell
moltis hooks list --eligible
```

### Security Baseline Check

```powershell
python scripts/moltis_security_check.py

# Strict flags
python scripts/moltis_security_check.py --expect-behind-proxy true --require-api-keys
```

### Hardened Profile

```powershell
Copy-Item .\config\moltis.hardened.example.toml $HOME\.config\moltis\moltis.toml
```

---

## Project Roadmap

| Phase | Status | Description |
|---|---|---|
| Phases 1â€“4 | âœ… Complete | MVP: collection, enrichment, reporting, hardening |
| Phoenix 1â€“2 | âœ… Complete | Frontend foundation + data layer |
| Phoenix 3 | âœ… Complete | Operations command center |
| Phoenix 4 | âœ… Complete | Reports module + workbench |
| Phoenix 5 | âœ… Complete | Sources + system pages |
| Phoenix 6 | âœ… Complete | Situation Analysis page, quality gate chart |
| Phoenix 7 | ðŸš§ In progress | FastAPI backend rewrite |
| Phoenix 8 | Planned | Real-time SSE updates |
| Phoenix 9 | Planned | Advanced features (global search, multi-workspace) |
| Phoenix 10 | Planned | 80% coverage, Playwright E2E, Lighthouse 90+ |

Active roadmap: `docs/roadmap/project-clarity-roadmap.md`

---

## Repository Layout

```
src/agent_hum_crawler/   # Python backend
  api/                   # FastAPI app + route modules (Phase 7)
  models.py              # SQLModel ORM
  coordinator.py         # Pipeline orchestrator
  situation_analysis.py  # OCHA SA generator
  graph_ontology.py      # Humanitarian ontology + NLP
  llm_provider.py        # LLM abstraction
scripts/
  dashboard_api.py       # HTTP bridge (legacy subprocess calls)
ui-phoenix/              # React 19 + TypeScript frontend (Project Phoenix)
config/                  # Country sources, feature flags, report templates, gazetteers
rust_core/               # PyO3 NLP extension
tests/                   # pytest suite (220+ tests)
artifacts/e2e/           # E2E gate artifacts
reports/                 # Generated report files (not committed)
```


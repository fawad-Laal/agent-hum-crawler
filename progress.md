# Progress Tracker - Dynamic Disaster Intelligence Assistant

Date: 2026-02-20
Last Updated: 2026-03-07
Status: Post-MVP Hardening + **Project Phoenix Phases 1-9 Complete** + **Phase 10.1 Coverage Infrastructure DONE** + **Phase 10.2 Bug-Fix Sprint DONE** (272 Vitest tests, 311 pytest tests, 0 TS errors)

## Overall Progress
- Documentation and specification phase: 100% complete
- MVP implementation phase: 100% complete
- Post-MVP hardening and operator tooling: in active rollout
- **Project Phoenix (Frontend Rewrite) Phase 1 — Foundation: COMPLETE**
- **Project Phoenix (Frontend Rewrite) Phase 2 — Data Layer: COMPLETE**
- **Project Phoenix (Frontend Rewrite) Phase 3 — Feature Pages (Operations): COMPLETE**
- **Project Phoenix (Frontend Rewrite) Phase 4 — Reports Module: COMPLETE**
- **Project Phoenix (Frontend Rewrite) Phase 5 — Sources & System: COMPLETE**
- **Project Phoenix (Frontend Rewrite) Phase 6 — Situation Analysis: COMPLETE**
- **Project Phoenix (Frontend Rewrite) Phase 7 — FastAPI Backend: direct-import migration complete, Redis caching added**
- **Project Phoenix (Frontend Rewrite) Phase 8 — Real-time Updates: SSE job stream, live job badge, loading toasts**
- **Phase 6.1 (R1) — Batch enrichment wired into `cycle.py`**: `enrich_events_batch()` is now primary path; single-item fallback on exception; `llm_mode=batch|single_fallback|disabled` in cycle stats/summary; 3 new batch enrichment tests (7/7 passing in `test_llm_enrichment.py`)
- Humanitarian ontology and Situation Analysis engine: implemented and validated
- Graph ontology evidence extraction: operational with multi-pattern NLP
- SA quality gate fixes (citation regex, date attribution, source labelling, raw text filter): applied 2026-03-02
- Iran gazetteer added (31 provinces + districts): 2026-03-02
- Roadmap updated with Phase 4B (Credibility Distribution) and Phase 4C (Conflict Emergency Improvements)
- `pyproject.toml` upgraded to v0.2.0 — added `fastapi`, `uvicorn[standard]`, `python-multipart` dependencies

## Project Phoenix — Frontend Rewrite (Phase 5)

### Phase 1 — Foundation (Week 1 of 3) — COMPLETE ✅
- [x] Initialized TypeScript + Vite 7 + React 19 project in `ui-phoenix/`
- [x] Installed and configured Tailwind CSS v4.2 with dark intelligence theme
- [x] Created Shadcn/ui primitives: Card, Badge, Button, Skeleton
- [x] Set up React Router 7 with 7 routes: `/`, `/operations`, `/reports`, `/sources`, `/system`, `/sa`, `/settings`
- [x] Built layout shell: Sidebar (collapsible), Header (with backend health badge), RootLayout
- [x] Ported KPI cards to Overview page: Cycles, Events, Dup Rate, Traceable, Hardening
- [x] Built Trend Charts (sparklines) on Overview page: Cycle Trends + Quality Rate Trends
- [x] Built Credibility Distribution and Source Health summary on Overview page
- [x] Created type-safe API client (`lib/api.ts`) mirroring all 15 dashboard_api.py endpoints
- [x] Created TanStack Query hooks (`hooks/use-queries.ts`) with auto-refresh and caching
- [x] Created Zustand UI store (`stores/ui-store.ts`) with localStorage persistence
- [x] Created comprehensive TypeScript types (`types/index.ts`) for all API response shapes
- [x] Created utility library (`lib/utils.ts`): cn, fmtNumber, fmtPercent, fmtDate, fmtRelativeTime
- [x] Set up Vitest with Testing Library: 21 tests, all passing
- [x] Reports page with live report listing from API
- [x] System page with E2E gate summary, hardening status, feature flags
- [x] Stub pages for Operations, Sources, SA, Settings (Phase 3-9)
- [x] Production build verified: 22KB CSS (4.7KB gz), 368KB JS (116KB gz) — under 400KB target
- [x] Parallel deploy configured: new app at `/v2`, old dashboard at `/dashboard`
- [x] Error boundaries on route components
- [x] Workbench route placeholder

### Phase 2 — Data Layer & Validation — COMPLETE ✅
- [x] Created Zod validation schemas (`lib/schemas.ts`) mirroring all API response shapes
- [x] Wired Zod runtime validation into `apiFetch` for all endpoints
- [x] Created Zustand form store (`stores/form-store.ts`) with localStorage persistence + migration
- [x] Created TanStack Query mutation hooks (`hooks/use-mutations.ts`): 9 mutations with cache invalidation
- [x] Created query key registry (`lib/query-keys.ts`) for centralized cache management
- [x] All 15 API endpoints type-safe with runtime validation

### Phase 3 — Feature Pages (Operations Module) — COMPLETE ✅
- [x] Refactored types to derive from Zod schemas via `z.infer<typeof schema>` (single source of truth)
- [x] Built `CountrySelect` multi-select chip component
- [x] Built `HazardPicker` multi-select chip component from system info
- [x] Built full `OperationsPage` (~740 lines) with collection form, action buttons, result display
- [x] Added Shadcn primitives: Input, Label, Separator, Switch, Collapsible
- [x] Added toast notifications (Sonner) for mutation feedback
- [x] Lazy-loaded route code splitting (Operations 28KB chunk, main bundle 470KB)
- [x] SA parameters panel (collapsible) with quality gate toggle
- [x] Full pipeline parameters panel (collapsible) with all fields
- [x] Source check result display with per-source status, freshness badges
- [x] SA result display with quality gate scores and markdown preview
- [x] Removed `/v2` basename — Phoenix runs standalone on port 5175
- [x] 55 tests passing, production build verified

### Phase 4 — Reports Module — COMPLETE ✅
- [x] Markdown renderer component (`components/ui/markdown-renderer.tsx`) — react-markdown + remark-gfm with full GFM table/list/code/blockquote styling
- [x] Report detail page (`features/reports/report-detail-page.tsx`) — full markdown rendering, metadata parsing (date, type, word count, section count)
- [x] Report export: Markdown download, HTML (standalone with marked.js), JSON (structured with sections/metadata), Copy to clipboard
- [x] Report workbench (`features/reports/report-workbench.tsx`) — side-by-side AI vs Deterministic compare with split/single view modes
- [x] Section word-budget analysis table with usage percentages and over-budget badges
- [x] Workbench parameters form (9 fields: countries, disaster types, template, max age, limits, caps)
- [x] Preset management modal (`features/reports/preset-manager-modal.tsx`) — save/load/delete workbench profiles via Dialog UI
- [x] Virtualized report list (`react-virtuoso`) — auto-engages at 50+ reports, search/filter with count badges
- [x] Tabbed layout: Reports listing + Workbench tabs
- [x] Route `/reports/:name` wired with lazy loading and code splitting
- [x] Vitest config fixed for ESM-only deps (react-markdown, remark-gfm) via `server.deps.inline`
- [x] 65 tests passing (17 Phase 4 tests), production build verified
- [x] Code-split bundles: reports-page 73KB (24KB gz), report-detail 7KB (3KB gz), markdown-renderer 159KB (48KB gz shared chunk)

### Phase 5 — Sources & System — COMPLETE ✅
- [x] Sources page: source health table with freshness indicators (`source-health-table.tsx`)
- [x] Connector diagnostics — collapsible per-connector cards (`connector-diagnostics.tsx`), unhealthiest first
- [x] Freshness trend chart — Recharts line chart sorted by age + stale threshold reference line (`freshness-trend-chart.tsx`)
- [x] Feature flags panel — toggle flags via API with pending/error feedback; widened to `boolean | number | string` values (`feature-flags-panel.tsx`)
- [x] Security baseline card — aggregates hardening gate + E2E security_status into pass/warn/fail/unknown (`security-baseline-card.tsx`)
- [x] System page — E2E gate summary, hardening gate, flags panel, security card (`system-page.tsx`)
- [x] Fixed `saQualityGateSchema` — backend returns a flat object (not array); old array schema caused ZodError on every SA call
- [x] Fixed `saResponseSchema` — `quality_gate` is now the correct object schema; `output_file` optional; `.passthrough()` for extra backend fields
- [x] Added `SAQualityGateDimension` type for Phase 6 per-dimension viz
- [x] 26 new Phase 5 tests; corrected 2 pre-existing incorrect schema tests
- [x] 103 tests total passing, 0 TypeScript errors

### Phase 6 — Situation Analysis — COMPLETE ✅
- [x] `SAQualityGateChart` — 6-dimension horizontal BarChart (Recharts); green ≥70%, yellow 50-69%, red <50%; overall score + PASS/FAIL badge; reference line at threshold
- [x] Full `SAPage` — template picker (OCHA Full SA, Default Report, Brief Update, Detailed Brief); form with all SA params (countries, hazards, event name/type/period, limits, LLM + quality gate toggles); collapsible form card
- [x] SA output panel — filename + word count + QG badge in header; Markdown download, HTML standalone export, Copy to clipboard
- [x] SA markdown preview with section TOC (tabs: Preview / Sections)
- [x] Fixed `quality_gate.details` ZodError — backend returns object (not array); `saQualityGateSchema.details` changed to `z.unknown()`
- [x] Fixed mutation toast lifecycle — all 5 mutations emit toasts at hook level so they survive page navigation
- [x] 22 new Phase 6 tests; 7/7 test files, 125 tests total, 0 TypeScript errors

### SA Empty Data Diagnosis (2026-03-04)
- **Root cause**: `src/agent_hum_crawler/crawler.db` is 0KB — no evidence collection runs have been executed
- **Effect**: SA runs with empty `processed_event` table → LLM generates boilerplate "no events" text → quality gate fails on key figure coverage, citation density, date attribution
- **Fix**: Run `agent-hum-crawler run-cycle --countries Lebanon --disaster-types conflict` first, then re-run the SA
- Lebanon sources ARE configured in `config/country_sources.json` (6 countries total)

### Phase 7 — FastAPI Backend — DIRECT-IMPORT MIGRATION COMPLETE ✅ (2026-03-04)
- [x] Created `src/agent_hum_crawler/api/` package — FastAPI application factory (`app.py`)
- [x] CORS middleware configured (Vite dev server :5175 + localhost:3000)
- [x] Route module stubs created under `src/agent_hum_crawler/api/routes/`:
  - `health.py` — `/api/health`
  - `overview.py` — `/api/overview`, `/api/system-info`
  - `cycle.py` — `/api/run-cycle`, `/api/source-check`
  - `reports.py` — `/api/reports`, `/api/report-content`
  - `situation_analysis.py` — `/api/write-situation-analysis`
  - `workbench.py` — `/api/report-workbench`
  - `db.py` — `/api/db/cycles`, `/api/db/events`, `/api/db/raw-items`, `/api/db/feed-health` *(new)*
  - `settings.py` — `/api/feature-flags`, `/api/update-feature-flag`
  - `jobs.py` — async job queue (`/api/jobs/<id>`, SSE-ready)
- [x] `job_store.py` — in-process async job store for long-running pipeline calls
- [x] API docs exposed at `/api/docs` (Swagger UI) and `/api/redoc`
- [x] `pyproject.toml` v0.2.0 with `fastapi`, `uvicorn[standard]`, `python-multipart` added
- [x] `dashboard_api.py` updated with FastAPI import path and 375-line refactor
- [x] Migrate all route stubs from subprocess CLI calls → direct Python module calls
  - `situation_analysis.py` route: replaced subprocess timestamp hack with `datetime.now(UTC)` directly
  - All other route modules (cycle, reports, workbench, overview, db, settings) already use direct imports
- [x] Redis job caching (optional stretch goal)
  - `RedisJobStore` class added to `job_store.py` — stores job state as Redis hashes with 24 h TTL
  - `_make_job_store()` factory: uses `RedisJobStore` when `REDIS_URL` env var is set, transparently falls back to in-process `JobStore` if Redis connection fails
  - `redis>=5.2.0` added as `[project.optional-dependencies] redis` in `pyproject.toml`
  - Install with: `pip install -e .[redis]`
- [x] `GET /api/feature-flags` endpoint added to `settings.py` (returns all flags; complements existing `POST /api/feature-flags` for updates)
- [ ] JWT/API-key auth middleware

### Data Browser Page (2026-03-04)
- [x] `ui-phoenix/src/features/data/data-page.tsx` (625 lines) — Database Explorer
  - Tabbed view: Cycle Runs · Events · Raw Items · Feed Health
  - Live data via `useDbCycles`, `useDbEvents`, `useDbRawItems`, `useDbFeedHealth` hooks
  - Inline search/filter per table, severity badges, freshness indicators
  - Refresh button with loading state
- [x] Route `/data` added to `routes.tsx` with lazy loading
- [x] Sidebar navigation link added (`Database` icon)
- [x] New query hooks + query keys + Zod schemas + TypeScript types added for all 4 DB endpoints

### Phase 8 — Real-time Updates — COMPLETE ✅ (2026-03-04)
- [x] Backend: `GET /api/jobs/{job_id}/stream` — SSE endpoint in `routes/jobs.py`
  - Pushes JSON status events every ~0.75 s until job reaches `done` or `error`
  - Keep-alive heartbeat comments (`": ping"`) every 15 s to survive proxy timeouts
  - `Cache-Control: no-cache`, `X-Accel-Buffering: no` headers set
  - Hard 20-minute timeout; graceful close on job record loss
- [x] Frontend: `stores/jobs-store.ts` — Zustand store tracking active jobs across navigation
  - `addJob / updateJob / removeJob / activeCount()`
  - Not persisted (in-memory only — jobs are transient by definition)
- [x] Frontend: `hooks/use-job-stream.ts` — `useJobStream<T>(jobId, label)` hook
  - Opens `EventSource` at `/api/jobs/{jobId}/stream`
  - Returns `{ status, result, error, isActive }` live state
  - Registers/updates/removes job in the jobs store
  - Cleans up EventSource on unmount
- [x] Frontend: `components/ui/global-job-badge.tsx` — header badge
  - Reads jobs store, renders nothing when no jobs are active
  - Animated pulse + `Loader2` spinner while jobs run
  - Shows job label or "N jobs running" for multiple concurrent jobs
- [x] Frontend: `components/layout/header.tsx` — `GlobalJobBadge` added to header
- [x] Frontend: `hooks/use-mutations.ts` — loading toasts for all 5 long-running mutations
  - `onMutate` → `toast.loading(…, { id })` + `addJob` to jobs store
  - `onSuccess` → `toast.success(…, { id })` + `removeJob`
  - `onError` → `toast.error(…, { id })` + `removeJob`
  - Stable toast IDs (`TOAST.cycle`, `TOAST.report`, `TOAST.sa`, `TOAST.pipeline`, `TOAST.sourceCheck`)
- JWT/API-key auth middleware — deferred

### Phase 9 — Analysis-Driven Intelligence & Observability — COMPLETE ✅ (2026-03-06)
- [x] 9.1 ReliefWeb fields + narrative merge (body_html, embedded figures, source credibility)
- [x] 9.2 MIME-first attachment parsing via MarkItDown (`attachment_extract.py`)
- [x] 9.3 Extraction telemetry: per-field hit/miss counters, cycle summary stats
- [x] 9.4 Diagnostics API + CLI (`/api/diagnostics/extraction`, `run-source-check --diagnostics`)
- [x] 9.5 Phoenix diagnostics UI (ExtractionTelemetryCard, SourceDiagnosticsPanel)
- [x] 9.6 API/job observability: adaptive polling, elapsed timings, per-operation status
- [x] 9.7 Orchestration consolidation: job_type enum, LLM semaphore (R14), TTL purge (R15)
- [x] 9.8 Security baseline semantics: `critical` state (R17), `deriveLevel()`, tooltips for all 5 states
- [x] 9.9 Rust/Python NLP alignment: `classify_all_impact_types` PyO3 export, `nlp_keywords.toml` single source, `build.rs` codegen, 34 drift-guard tests, left-boundary keyword matching
- **Totals: 129 Vitest tests (0 TS errors), 305 pytest tests**

### Future Phase (10)
- **Phase 10 — Testing & Release**: 80% coverage, Playwright E2E, Lighthouse 90+, WCAG 2.1 AA, production deployment

#### Phase 10.1 — Coverage Infrastructure & Unit Tests (2026-03-07)
- [x] Installed `@vitest/coverage-v8@4.0.18` (provider matching vitest version)
- [x] Added `coverage` config block to `vite.config.ts`: provider v8, include `src/**/*.{ts,tsx}`, exclude `main.tsx`/`vite-env.d.ts`
- [x] `tests/unit/api-client.test.ts` — 30 tests covering `lib/api.ts`: apiFetch success/error/schema-fail, pollJob done/error/back-off, all 12 GET functions, all 10 POST functions including 202+pollJob pattern
- [x] `tests/unit/stores.test.ts` — 19 tests covering `stores/jobs-store.ts` (14 tests: addJob, updateJob, removeJob, getJob, activeCount, full lifecycle) and `stores/ui-store.ts` (5 tests: initial state, toggleSidebar, setSidebarOpen)
- [x] `tests/unit/query-keys.test.ts` — 16 tests covering all QUERY_KEYS static keys and factory functions
- [x] `tests/unit/hooks.test.tsx` — 32 tests covering all 10 mutation hooks (`use-mutations.ts`) and all 12 query hooks (`use-queries.ts`) including DB hooks (useDbCycles, useDbEvents, useDbRawItems, useDbFeedHealth)
- [x] `tests/unit/layout-components.test.tsx` — 27 tests covering `ErrorBoundary` (reset, custom fallback), `Header` (health states, refresh), `Sidebar` (open/collapsed, toggle), `RootLayout` (title derivation, ml-60/ml-16), `GlobalJobBadge` (null/single/multi-job, elapsed timer)
- [x] Coverage thresholds ratcheted: stmts 51%, branches 43%, funcs 43%, lines 53%
- **Totals: 12 test files, 253 tests (up from 194), 0 TypeScript errors**
- **Coverage: stmts 51.3% / branches 43.13% / funcs 43.4% / lines 53.11% (up from 41.65%/37.9%/32.65%/42.89%)**
- **Key files now at 100%: header.tsx, root-layout.tsx, sidebar.tsx, global-job-badge.tsx, use-queries.ts, query-keys.ts, jobs-store.ts, ui-store.ts, error-boundary.tsx**

#### Phase 10.2 — Bug-Fix Sprint (2026-03-07) ✅

All 7 bugs from roadmap items 10A and 6B fixed in strict sequence. Operating rule applied throughout: *no item accepted as complete without measurable acceptance evidence*.

**10A.1 / 6B.1 — Missing `/api/db/extraction-diagnostics` route**
- [x] Added `GET /api/db/extraction-diagnostics` endpoint to `src/agent_hum_crawler/api/routes/db.py`; proxies to existing `build_extraction_diagnostics_report()` in `database.py`
- [x] Acceptance: 2 new `useExtractionDiagnostics` tests in `hooks.test.tsx` (params forwarding + response structure) ✅

**10A.3 — Real backend job_id threading**
- [x] All 7 long-running functions in `api.ts` accept optional `onJobQueued?: (jobId: string) => void` callback fired after the 202 is received
- [x] All 5 mutation hooks in `use-mutations.ts` use `useRef<string | null>` to capture the real backend `job_id`; `addJob()` and `removeJob()` now use the real id (not the `TOAST.*` placeholder)
- [x] `onMutate` emits `toast.loading` only; `onJobQueued` callback registers the real id in the jobs store
- [x] Acceptance: 2 new tests in `hooks.test.tsx` — "registers REAL backend job_id" + "removes job by real backend job_id" ✅

**6B.2 — Job TTL cleanup**
- [x] Added `job.completed_at = time.monotonic()` in both `done` and `error` branches of `job_store.py`'s `_run()`
- [x] Added `_purge()` method (evicts completed/error jobs older than `_IN_PROCESS_JOB_TTL = 300 s`)
- [x] `_purge()` called inside `submit()` under the lock before adding the new job

**10A.2 — Feature-flag type coercion**
- [x] Replaced `Boolean(rawValue)` in `feature-flags-panel.tsx` with type-aware `isBoolLike` / `enabled` logic covering `boolean`, `0/1` numeric, `"true"/"false"` string, and `"0"/"1"` string (old `Boolean("false") === true` bug fixed)
- [x] Render logic: Switch for bool-like values; `<Badge variant="secondary">` showing `String(rawValue)` for non-bool-like values
- [x] Acceptance: 9 coercion tests + 3 structure tests in new `feature-flags-panel.test.tsx` (12/12) ✅

**10A.4 — Toast ownership moved to hook**
- [x] `useUpdateFeatureFlag` in `use-mutations.ts` now owns the full toast lifecycle (`onMutate` loading, `onSuccess` success, `onError` error) using stable id `TOAST.featureFlag`
- [x] Removed `toast` import and per-call `onSuccess`/`onError` callbacks from `feature-flags-panel.tsx`; `toggle()` call simplified
- [x] Acceptance: 3 new tests in `hooks.test.tsx` — loading/success/error toast ownership ✅

**10A.5 — Targeted tests**
- [x] `hooks.test.tsx`: 39 tests total (was 32); 7 new tests covering 10A.1 contract (×2), 10A.3 real job_id (×2), 10A.4 toast ownership (×3)
- [x] `feature-flags-panel.test.tsx`: new file, 12/12 tests passing — bool coercion (×9), structure/UX (×3)

**6B.3 — Centralize storage path**
- [x] Added `get_data_root() -> Path` to `database.py` — respects `MOLTIS_DATA_ROOT` env var, falls back to `~/.moltis/agent-hum-crawler`
- [x] `default_db_path()` now delegates to `get_data_root()`
- [x] Deleted `_db_path()` from `routes/db.py` — replaced with `default_db_path()` import
- [x] Deleted `_monitoring_db_path()` from `scripts/dashboard_api.py` — replaced with `default_db_path()` import
- [x] Single hardcoded path string across all three files eliminated
- [x] Acceptance: 3 new pytest tests — default path, env override, `default_db_path()` composition ✅

**6B.4 — Schema drift verification**
- [x] Added `verify_schema_drift(path: Path | None = None) -> list[str]` to `database.py`
- [x] Opens DB read-only (`?mode=ro`); compares SQLModel metadata tables + columns against live `sqlite_master` / `PRAGMA table_info`
- [x] Returns list of `"Missing table: <name>"` / `"Missing column: <table>.<col>"` strings; empty list = in-sync
- [x] Safe to call at startup; table names come from SQLModel metadata (not user input)
- [x] Acceptance: 3 new pytest tests — no-db warning, in-sync returns `[]`, detects missing column ✅

**Test totals after Phase 10.2:**
- Frontend (Vitest): **272 tests, 13 test files, 0 TS errors** (up from 253 / 12 files)
  - hooks.test.tsx: 39/39 ✅
  - feature-flags-panel.test.tsx: 12/12 ✅ (new file)
- Backend (pytest): **311 tests** (up from 305; +6 in test_database.py)
  - test_database.py: 8/8 ✅

## Completed
- Milestones 1-5 completed.
- 7-cycle pilot executed for Milestone 6.
- Added `pilot-run` command to automate multi-cycle evidence generation (`quality_report`, `source_health`, `hardening_gate`).
- Added `conformance-report` command to combine hardening gate with Moltis integration checks.
- Added LLM enrichment telemetry in cycle output and `quality-report` (enrichment rate, citation coverage, provider/validation failures).
- Added `llm-report` command and LLM quality thresholds to hardening gate.
- Dedupe/cycle flow now suppresses unchanged events from persisted cycle outputs to prevent duplicate-rate inflation.
- Added `pilot-run --reset-state-before-run` for reproducible high-yield pilot windows.
- Final conformance verification completed (`conformance-report`: pass).
- Post-MVP Phase A hook baseline now active in Moltis user hook registry (`~/.moltis/hooks/*`): `ahc-llm-tool-guard`, `ahc-tool-safety-guard`, `ahc-audit-log`.
- Runtime confirmation captured from startup logs: `7 hook(s) discovered (4 shell, 3 built-in), 6 registered`.
- Hook safety checks validated:
  - `BeforeToolCall` blocks destructive command sample (`rm -rf /`).
  - `BeforeLLMCall` blocks injection-escalation sample.
  - `Command` audit event written to `.moltis/logs/hook-audit.jsonl`.
- Post-MVP Phase B completed with hardened Moltis profile template:
  - `config/moltis.hardened.example.toml`
  - rollout steps documented in `README.md`
- Post-MVP Phase C baseline started:
  - Skill/session governance SOP added (`specs/16-phase-c-skill-branch-sop.md`).
  - `delete_skill` now requires explicit confirmation contract in hook policy.
  - Guard tests added in `tests/test_hook_policies.py`.
  - Live incident branch workflow executed in Moltis on `2026-02-18`:
    - Fork created from `main` using label `incident-madagascar-cyclone-20260218-alt-severity`.
    - Child session key: `session:86f57658-2647-4cea-9be7-8f219224f38c`.
    - Merge-back summary message sent in parent session (`chat.send` after switching back to `main`).
    - Persisted fork evidence verified in `~/.moltis/moltis.db` (`sessions.parent_session_key=main`, `fork_point=0`).
- Post-MVP Phase D baseline implemented:
  - Added local validation gate scripts:
    - `scripts/local-validate.ps1`
    - `scripts/local-validate.sh`
  - Gate checks now include `pytest -q` and `compileall` for `src/tests`.
  - Usage documented in `README.md`.
- Phase D extended to full deterministic E2E regression gate:
  - Added `scripts/e2e_gate.py`.
  - `local-validate` now runs replay/report/hardening/conformance E2E steps.
  - Artifacts captured to `artifacts/e2e/<UTC timestamp>/`.
  - Report-quality enforcement verified in E2E (`report_quality_status=pass`).
- LLM Intelligence Layer v1 expansion started with GraphRAG reporting:
  - Added graph-style retrieval from SQLite evidence (`src/agent_hum_crawler/reporting.py`).
  - Added long-form report generation command:
    - `python -m agent_hum_crawler.main write-report ...`
  - Added deterministic report test coverage (`tests/test_reporting.py`).
  - Added report quality gates and enforcement:
    - citation density threshold
    - section completeness checks
    - unsupported-claim checks (incident blocks must include source URL)
    - CLI enforce mode: `--enforce-report-quality`
  - E2E gate now enforces report quality via `write-report`.
- KPI commands operational and validated:
  - `quality-report`
  - `source-health`
  - `hardening-gate`
- Parser hardening and source-health telemetry validated in live cycles.
- Reporting stack upgraded to template-driven formatting with editable section/length controls:
  - `config/report_template.json` (default)
  - `config/report_template.brief.json` (short donor update)
  - `config/report_template.detailed.json` (long analyst brief)
- `write-report` now supports `--report-template` and loads `.env` before report generation.
- AI report path hardened:
  - true `llm_used` detection (actual AI use, not just flag),
  - `AI Assisted: Yes` banner when AI drafting is used,
  - OpenAI Responses structured output parsing fixed.
- Citation + format consistency improved:
  - numbered citation refs in body (`[1]`, `[2]`),
  - numbered `## Citations` list at end,
  - template-enforced section naming to keep AI and deterministic outputs aligned.
- Security/auth hardening rollout started (item 1):
  - Added automated baseline verifier: `scripts/moltis_security_check.py`.
  - Extended to capture auth/proxy matrix evidence and scoped API-key verification from `~/.moltis/moltis.db`.
  - Validates live Moltis config for auth enabled, non-`never` approval mode, hardened sandbox mode, metrics/prometheus on, hooks present, and credentials configured.
  - Supports strict rollout flags:
    - `--expect-behind-proxy true|false|auto`
    - `--require-api-keys`
  - Latest run result: `status=pass` against:
    - `C:\Users\Hussain\.config\moltis\moltis.toml`
    - `C:\Users\Hussain\.moltis\moltis.db`
  - Wired into deterministic E2E gate artifacts:
    - `artifacts/e2e/<timestamp>/06_moltis_security_check.json`
    - summary now includes `security_status`
- Source expansion/hardening updates:
  - Added BBC, Al Jazeera English, AllAfrica, Africanews, ANA, The Guardian, Reuters feeds.
  - Replaced failing ANA/Reuters URLs with stable working endpoints.
  - Adjusted source-health aggregation so `recovered` parse status is not counted as feed failure.
- Added minimal local observability UI for crawler/report iteration:
  - API bridge: `scripts/dashboard_api.py`
  - React dashboard scaffold: `ui/` (Vite + React)
  - Supports run-cycle, write-report, KPI snapshot, and report preview flows.
- Added dedicated frontend roadmap:
  - `specs/frontend-roadmap.md` (phased UI plan from baseline dashboard to operator-grade console).
- Frontend Phase 1 (operator monitoring) started:
  - trend charts for cycle/LLM and rolling quality rates,
  - hardening threshold panel (actual vs threshold),
  - conformance/security snapshot from latest E2E artifacts,
  - source-health hotspot table (highest failure rates first).
- Frontend Phase 2 (report quality workbench) started:
  - one-click deterministic vs AI report compare (`/api/report-workbench`),
  - side-by-side quality metric diagnostics in UI,
  - section word-budget usage table from template limits,
  - side-by-side markdown preview for quick editorial review.
  - reusable compare presets (save/load/delete) with persisted store.
  - one-click `Rerun Last Profile` for repeatable QA/report iteration.
- Input robustness and operator clarity improvements:
  - disaster-type alias normalization added across runtime config and reporting filters (e.g. `Floods` -> `flood`, `Cyclones` -> `cyclone/storm`).
  - UI now shows explicit last-action status (success/fail) and clearer in-flight button states during cycle/report runs.
- Added date-range and source-by-source verification controls:
  - runtime/report `max_age_days` support to suppress stale evidence windows,
  - new `source-check` CLI command for one-by-one feed diagnostics,
  - dashboard API/UI support for source checks (`/api/source-check`) with working/non-working status per source.
- Added centralized feature-flag system:
  - `src/agent_hum_crawler/feature_flags.py`
  - `config/feature_flags.json` (+ example template)
  - runtime toggles now read from centralized flags (with env overrides)
  - dashboard now surfaces active flags in overview.
- Source diagnostics and freshness hardening added:
  - per-source freshness status (`fresh` / `stale` / `unknown`) computed against `max_age_days`,
  - per-source match reason diagnostics (`country_miss`, `hazard_miss`, `age_filtered`),
  - stale source streak tracking with policy-based warn/demote actions,
  - source-check/run-cycle payloads now expose warnings + stale/demoted source counts.
- Report retrieval quality controls added:
  - canonical citation URL pipeline (`url` + `canonical_url`) across raw items and events,
  - citations/domain diversity now prefer canonical publisher URLs when available,
  - country-balance selector in GraphRAG retrieval (`country_min_events`),
  - connector/source caps (`max_per_connector`, `max_per_source`) to reduce local-feed dominance,
  - connector weighting boost for humanitarian connectors (UN/ReliefWeb) in scoring.
- Source integration improvements completed:
  - ReliefWeb upgraded to API v2 reports endpoint with preset/query payload generation from runtime filters.
  - GDACS upgraded from generic feed to hazard-specific feeds (`all_7d`, `floods_7d`, `cyclones_7d`) from feed reference docs.
  - FEWS NET RSS integration added (`Analysis Note`, `Weather and Agriculture Outlook`) from `fews.net/feeds`.
- Dashboard/operator controls extended for retrieval tuning:
  - `Country Min Events`, `Max / Connector`, `Max / Source` wired into write-report/workbench flows.
- Local/news source set refined for relevance:
  - removed stale CNN World default feed,
  - added country-targeted disaster query feeds for Madagascar, Mozambique, Pakistan, Bangladesh, Ethiopia,
  - retained BBC, Reuters World, NYT World, NPR World, Al Jazeera, AllAfrica, Africanews, ANA, Guardian.
- Current test status: `220 passed`.
- Dashboard redesigned from 13 sections → 8 unified sections (Command Center, Trends, System Health, Action Output, Source Intelligence, Workbench, SA Output, Reports).
- SA quality analysis completed — root cause analysis of Ethiopia SA output quality issues documented in `docs/analysis/sa-improvement-analysis.md`.
  - Identified 9 critical SA issues: garbage sector tables, missing gazetteers, no date awareness, PDFs not extracted, figure deduplication absent, etc.
  - Proposed multi-agent architecture (5 agent types), OCR pipeline (Docling primary), Graph RAG enhancements, model selection strategy.
  - 5-phase implementation roadmap defined.

## Humanitarian Ontology & Situation Analysis (New)
- Built graph ontology module (`src/agent_hum_crawler/graph_ontology.py`) for structured humanitarian evidence modelling:
  - `HumanitarianOntologyGraph` with typed nodes: `HazardNode`, `ImpactObservation`, `NeedStatement`, `ResponseAction`, `RiskStatement`, `AdminArea`.
  - Multi-pattern NLP figure extraction (`_extract_figures`) with 4 regex patterns:
    - Standard `NUM keyword` (e.g. "48,000 displaced")
    - Death toll phrasing (e.g. "death toll rises to 59")
    - At-least/over/approximately phrasing (e.g. "at least 52 dead")
    - Sentence-level pattern (e.g. "59 killed in the storm")
  - Uses `max()` accumulation to avoid double-counting across overlapping patterns.
  - Automatic impact type, need type, hazard category, and admin area classification from text.
  - Country gazetteer system (`COUNTRY_GAZETTEERS`) with admin1/admin2 hierarchies:
    - Madagascar: 22 provinces, 100+ districts
    - Mozambique: 10 provinces, 50+ districts
  - Auto-detects countries from evidence and loads matching gazetteers when no explicit hierarchy is provided.
- Built OCHA-style Situation Analysis renderer (`src/agent_hum_crawler/situation_analysis.py`):
  - 15-section report structure following OCHA SA format.
  - Template-driven rendering from `config/report_template.situation_analysis.json`.
  - Deterministic path renders structured tables and evidence-sourced narratives without LLM dependency.
  - Optional LLM narrative generation across all sections.
  - Auto-inference of event name and type from evidence (e.g. "Cyclone Gezani" detected from headlines).
  - Auto-inference of disaster type (e.g. "cyclone" → "Tropical Cyclone").
  - Dynamic access constraint extraction from evidence using keyword patterns.
  - Sector narrative rendering maps evidence descriptions instead of static "Assessment pending" placeholders.
  - Full admin reference annex auto-generated from country gazetteers.
  - CLI: `write-situation-analysis` subcommand.
  - SA template: `config/report_template.situation_analysis.json`.
- Wired Situation Analysis into dashboard API and frontend:
  - API endpoint: `POST /api/write-situation-analysis` in `scripts/dashboard_api.py`.
  - Frontend: collapsible "Situation Analysis Parameters" form in `ui/src/App.jsx`.
  - Fields: SA Title, Event Name, Event Type, Period, SA Template, SA Limit Events.
  - One-click "Write Situation Analysis" button with output display.
- Fixed dashboard API list-to-string serialization for countries/disaster_types parameters.
- Validated SA output quality — report now includes:
  - Event card with auto-detected "Cyclone Gezani" and "Tropical Cyclone" type.
  - Key figures: Deaths 158, Displaced 16,000, Affected Population 400,052, Severity Phase 4.
  - Evidence-sourced sector narratives (Health, Food Security).
  - Full 22-province admin annex with districts for Madagascar.
  - 12 source citations.

## Milestone Status (from `specs/05-roadmap.md`)
- Milestone 1 (Week 1): Completed
- Milestone 2 (Week 2): Completed
- Milestone 3 (Week 3): Completed
- Milestone 4 (Week 4): Completed
- Milestone 5 (Week 5): Completed
- Milestone 6 (Week 6): Completed (pilot, hardening, LLM quality, conformance all passed)

## Pilot Snapshot
- `cycles_analyzed`: 7
- `events_analyzed`: 2
- `duplicate_rate_estimate`: 0.0 (fixed)
- `hardening-gate` status: `pass`
- `llm-report --enforce-llm-quality`: `pass`
- `conformance-report` status: `pass`

## Next Action Queue — Project Clarity

Active roadmap: `docs/roadmap/project-clarity-roadmap.md`

1. **~~Reduced++ Phase 1 — Foundation~~ ✅ COMPLETE**:
   - ✅ ReliefWeb pagination + appname enforcement + date filter.
   - ✅ PDF text extraction (pdfplumber + pypdf) wired into ReliefWeb.
   - ✅ Country substring matching fixed (word-boundary regex).
   - ✅ Dynamic gazetteer system (50+ countries, LLM generation, file caching).
   - ✅ Strict JSON schema on SA LLM calls (11 keys, strict mode).
   - ✅ Deterministic sector tables (no raw evidence in cells).
   - ✅ Event name inference fixed (3-pass: storm → crisis → type+country).
   - ✅ `published_at` + `source_label` in LLM evidence digest.
2. **~~Reduced++ Phase 2 — Intelligence Layer~~ ✅ COMPLETE**:
   - ✅ Temporal layer on ontology nodes (`reported_date` + `source_label` on ImpactObservation, NeedStatement, RiskStatement).
   - ✅ Figure deduplication (MAX-per-(geo_area, figure_key) in national/admin1/admin2 aggregation).
   - ✅ Batch enrichment (`enrich_events_batch()`, 15 items/call, strict JSON schema, single-event fallback).
   - ✅ Geo normalization (ISO3 through full pipeline: dedupe → database → reporting → ontology; `country_iso3` on ProcessedEvent, EventRecord, ReportEvidence, GeoArea).
   - ✅ Two-pass SA synthesis (Pass 1: core narrative — executive_summary, national_impact, access_constraints, outstanding_needs, forecast_risk; Pass 2: 6 sector narratives with Pass 1 context).
   - ✅ "As of" dating on all SA figures (`national_figures_with_dates()`, "As of" column in impact table, inline date attribution in narratives).
   - ✅ Streaming ingestion (`fetch_stream()` generator on ReliefWeb connector — yields `RawSourceItem` page-by-page).
3. **~~Reduced++ Phase 3 — Expansion~~ ✅ COMPLETE**:
   - ✅ Citation span locking (`validate_sa_citations()`, `strip_invalid_citations()`, LLM prompt citation index injection).
   - ✅ Expand gazetteers (Somalia, Sudan, South Sudan, DRC, Afghanistan — 5 new files in `config/gazetteers/`).
   - ✅ Source credibility tier weighting (`source_credibility.py` — 4-tier system: UN/OCHA → NGO/Gov → Major News → Other; wired into graph_ontology + reporting).
   - ✅ SA quality gate (`sa_quality_gate.py` — 6-dimension scoring: section completeness, key figure coverage, citation accuracy/density, admin coverage, date attribution; configurable thresholds).
   - ✅ Agent abstraction layer (`agents.py` — `Agent` base class with retry/validate/fallback lifecycle; `EnrichmentAgent`, `SANarrativeAgent`, `GazetteerAgent`, `BatchEnrichmentAgent`, `ReportNarrativeAgent`).
   - ✅ Provider abstraction (`llm_provider.py` — `LLMProvider` ABC, `OpenAIResponsesProvider` implementation, `get_provider()` singleton with `LLM_PROVIDER` env selection, `register_provider()` extension point).
   - ✅ Dashboard UI update for Phase 3 features:
     - Source Credibility Distribution panel with tier 1-4 horizontal bar chart (overview API via `credibility_distribution`).
     - SA Quality Gate scores panel (6-dimension bar visualization after SA generation).
     - Quality Gate toggle checkbox in SA Parameters form.
     - `--quality-gate` CLI flag wired through `write_situation_analysis()` → `render_situation_analysis()`.
     - New CSS: `.credibility-bars`, `.sa-quality-gate`, `.quality-dims` layouts.
4. **~~Reduced++ Phase 4 — Deep Extraction & Pipeline Orchestration~~ ✅ COMPLETE**:
   - ✅ PDF table extraction (`ExtractedTable`/`ExtractedDocument` dataclasses, pdfplumber table extraction with markdown conversion).
   - ✅ Full-article content fetching (PDF link detection from page HTML, RSS enclosure extraction, capped at 3 PDFs per article).
   - ✅ Multi-impact per evidence (`_classify_all_impact_types()` — all matching types, secondary gets `{}` figures to prevent double-counting).
   - ✅ Province-level figure distribution (`distribute_national_figures()` — proportional allocation by admin1 mention counts, distributed flag).
   - ✅ Coordinator pipeline upgrade (`_run_stage()` wrapper, `ProgressCallback`, per-stage error/diagnostics, resilient pipeline, 3-state status).
   - ✅ Ontology persistence in DB (5 new SQLModel tables: `OntologySnapshot`, `ImpactRecord`, `NeedRecord`, `RiskRecord`, `ResponseRecord`; `persist_ontology()` + `get_ontology_snapshots()` for trending).
5. **Phase 5 — Frontend Rewrite (Project Phoenix)** — PLANNED:
   - Complete rewrite of 1795-line monolithic dashboard addressing 5 critical architectural issues.
   - 10-phase implementation: Foundation → Data Layer → Operations → Reports → Sources/System → SA → Backend (FastAPI) → Real-time (SSE) → Advanced Features → Testing/Release.
   - Target stack: TypeScript + Shadcn/ui + React Router + TanStack Query + Zustand + FastAPI + Redis.
   - Timeline: 24 weeks (6 months) with 1-2 developers.
   - Deliverables: 60-80 components, 80%+ test coverage, 100+ concurrent user support, < 500ms API latency, 90+ Lighthouse score.
   - Documentation: `docs/roadmap/frontend-rewrite-roadmap.md`, audit: `docs/analysis/frontend-audit-report.md`.
6. Continue security/auth hardening rollout from `specs/13-moltis-security-auth.md`.
5. Continue streaming/tool-registry conformance rollout from `specs/14-moltis-streaming-tool-registry.md`.
6. Continue frontend roadmap execution (archived: `docs/roadmap/archive/frontend-roadmap.md`).

## Analysis Documents
- `docs/analysis/sa-improvement-analysis.md` — Comprehensive SA quality analysis (multi-agent proposal superseded by Reduced++).
- `docs/roadmap/project-clarity-roadmap.md` — **Active** — Project Clarity (SA Reduced++ Architecture).
- `docs/roadmap/README.md` — Roadmap index (active + archived phases).

## Risks / Blockers
- No blocking issues for MVP sign-off.

## References
- `docs/roadmap/project-clarity-roadmap.md` (active roadmap)
- `docs/roadmap/README.md` (roadmap index)
- `specs/05-roadmap.md` (closed — archived)
- `specs/09-stocktake.md`
- `specs/10-pilot-signoff.md`

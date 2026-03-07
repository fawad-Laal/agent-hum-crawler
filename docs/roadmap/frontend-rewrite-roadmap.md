# Frontend Rewrite Roadmap â€” Agent HUM Crawler

**Date:** March 7, 2026  
**Status:** Active - Phases 1-9 complete in codebase; Phase 10 and review-driven remediation open  
**Codename:** Project Phoenix  
**Predecessor:** Original Dashboard (1795-line monolith in [ui/src/App.jsx](../../ui/src/App.jsx))  
**Audit Report:** [Frontend Audit Report](../analysis/frontend-audit-report.md)  
**Review Baseline:** [Whole App Review - March 2026](../analysis/whole-app-review-march2026.md)

---

## 1. Executive Summary

This roadmap defines a **complete frontend rewrite** for the Agent HUM Crawler platform, transitioning from a 1795-line monolithic React component to a scalable, maintainable, production-grade web application.

**Why Rewrite Instead of Refactor:**
- Current codebase has **5 critical architectural issues** that cannot be incrementally fixed
- Technical debt accumulated to unsustainable levels (19 useState hooks, 0 component decomposition)
- Foundational patterns (no routing, no data fetching library, manual state management) require complete replacement
- Rewrite timeline (5-6 months) comparable to incremental refactor with better outcome

**Strategic Objectives:**
1. **Scalability** â€” Support 50+ countries, 1000+ reports, 100+ concurrent users
2. **Maintainability** â€” Enable 5-10 developers to work in parallel without conflicts
3. **User Experience** â€” Real-time updates, advanced search/filter, responsive design
4. **Production Readiness** â€” Authentication, monitoring, error recovery, data export
5. **Developer Velocity** â€” Type safety, component library, testing infrastructure

---

## 2. Current State Assessment

### 2.1 Architecture Issues

| Issue | Evidence | Impact |
|-------|----------|--------|
| **Monolithic Component** | 1795-line [App.jsx](../../ui/src/App.jsx), 0 component files | Merge conflicts, 3-5x slower onboarding |
| **State Chaos** | 19 useState hooks, no abstraction | Impossible to track dependencies, lost work on refresh |
| **No Data Layer** | 15 hand-rolled fetch functions | Race conditions, no caching, stale data |
| **No Navigation** | 8 sections in vertical scroll | Information overload, no deep linking |
| **Backend Bottleneck** | ThreadingHTTPServer + subprocess calls | 5-30s latency, cannot scale past 20 users |

### 2.2 Scalability Limits

| Dimension | Current Limit | Breaks At | Rewrite Target |
|-----------|---------------|-----------|----------------|
| **Data Volume** | 100 sources, 100 reports | 1000+ items (no virtualization) | 10,000+ items |
| **Concurrent Users** | 1-5 users | 20+ users (ThreadingHTTPServer) | 100+ users |
| **Developers** | 1 developer | 5+ devs (single-file conflicts) | 10+ devs in parallel |
| **Features** | 8 sections | 15+ sections (vertical scroll overload) | Modular tabs/routing |

### 2.3 Technical Debt Metrics

- **Lines of Code:** 1795 (App.jsx) + 649 (styles.css) + 720 (dashboard_api.py) = **3164 LOC**
- **Components:** 1 (App) + 1 utility (TinyLineChart) = **2 components**
- **State Variables:** 19 useState hooks
- **API Calls:** 15 fetch functions
- **Test Coverage:** 0%
- **Type Safety:** 0% (no TypeScript)

---

## 3. Target Architecture

### 3.1 Technology Stack

#### Frontend

| Layer | Current | Target | Rationale |
|-------|---------|--------|-----------|
| **Framework** | React 18.3.1 | React 18.3+ | Keep (mature, team familiarity) |
| **Build Tool** | Vite 5.4 | Vite 6.x | Upgrade (faster HMR, better DX) |
| **Language** | JavaScript | TypeScript 5.x | Type safety, refactoring confidence |
| **Routing** | None | React Router 7.x | Deep linking, code splitting |
| **State** | 19 useState | Zustand + TanStack Query | Centralized state + server cache |
| **Forms** | Manual spreading | React Hook Form + Zod | Validation, less boilerplate |
| **UI Library** | Custom CSS | Shadcn/ui + Tailwind | Design system, accessibility |
| **Data Viz** | Custom SVG | Recharts | Charts, graphs, sparklines |
| **Testing** | None | Vitest + Testing Library | Unit + integration tests |

#### Backend

| Layer | Current | Target | Rationale |
|-------|---------|--------|-----------|
| **Server** | ThreadingHTTPServer | FastAPI + Uvicorn | ASGI, WebSocket support, OpenAPI |
| **Architecture** | Subprocess CLI calls | Direct Python imports | 10-50x faster, no process overhead |
| **Caching** | None | Redis | Reduce DB load, faster overview |
| **Auth** | None | JWT + OAuth2 | Multi-user support |
| **Real-time** | Polling | Server-Sent Events (SSE) | Live updates without polling |
| **Monitoring** | None | Prometheus + Grafana | Observability, alerting |

### 3.2 Application Structure

```
ui/
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ components/          # Reusable UI components
â”‚   â”‚   â”œâ”€â”€ layout/          # Header, Sidebar, Layout shells
â”‚   â”‚   â”œâ”€â”€ charts/          # TrendChart, BarChart, Sparkline
â”‚   â”‚   â”œâ”€â”€ forms/           # CountrySelect, HazardPicker, DateRange
â”‚   â”‚   â”œâ”€â”€ tables/          # DataTable, SourceTable, ReportTable
â”‚   â”‚   â””â”€â”€ ui/              # Shadcn/ui primitives (Button, Card, etc.)
â”‚   â”œâ”€â”€ features/            # Feature modules
â”‚   â”‚   â”œâ”€â”€ overview/        # Dashboard home (KPIs, trends)
â”‚   â”‚   â”œâ”€â”€ operations/      # Run Cycle, Source Check, Collection
â”‚   â”‚   â”œâ”€â”€ reports/         # Write Report, Report List, Preview
â”‚   â”‚   â”œâ”€â”€ situation-analysis/ # Write SA, SA Output, Quality Gate
â”‚   â”‚   â”œâ”€â”€ workbench/       # AI vs Deterministic, Presets, Compare
â”‚   â”‚   â”œâ”€â”€ sources/         # Source Health, Connector Diagnostics
â”‚   â”‚   â”œâ”€â”€ system/          # Hardening, E2E, Security, Conformance
â”‚   â”‚   â””â”€â”€ settings/        # User Preferences, Feature Flags
â”‚   â”œâ”€â”€ hooks/               # Custom hooks (useOverview, useSources, etc.)
â”‚   â”œâ”€â”€ lib/                 # Utilities, API client, validators
â”‚   â”œâ”€â”€ stores/              # Zustand stores (formStore, uiStore)
â”‚   â”œâ”€â”€ types/               # TypeScript types
â”‚   â”œâ”€â”€ routes.tsx           # Route definitions
â”‚   â”œâ”€â”€ App.tsx              # Root component (Router + Layout)
â”‚   â””â”€â”€ main.tsx             # Entry point
â”œâ”€â”€ public/                  # Static assets
â”œâ”€â”€ tests/                   # Frontend tests
â”‚   â”œâ”€â”€ unit/                # Component unit tests
â”‚   â”œâ”€â”€ integration/         # Feature integration tests
â”‚   â””â”€â”€ e2e/                 # Playwright E2E tests (future)
â”œâ”€â”€ package.json
â”œâ”€â”€ tsconfig.json
â”œâ”€â”€ vite.config.ts
â””â”€â”€ tailwind.config.js
```

### 3.3 Component Breakdown

| Old Section (App.jsx) | New Feature Module | Routes | Components |
|-----------------------|-------------------|--------|------------|
| Command Center (L633-L1035) | `features/operations/` | `/operations` | OperationsPage, CollectionForm, ActionButtons, ParameterPanel |
| KPIs (L613-L630) | `features/overview/` | `/` (home) | OverviewPage, KPICards, MetricCard |
| Trends (L1038-L1095) | `features/overview/` | `/` | TrendCharts, CycleTrend, QualityTrend |
| System Health (L1098-L1252) | `features/system/` | `/system` | SystemHealthPage, HardeningPanel, ConformancePanel, FeatureFlagsPanel |
| Source Intelligence (L1357-L1567) | `features/sources/` | `/sources` | SourcesPage, SourceTable, ConnectorDiag, FreshnessChart |
| Workbench (L1712-L1727) | `features/workbench/` | `/workbench` | WorkbenchPage, CompareView, PresetManager, QualityMetrics |
| SA Output (L1730-L1769) | `features/situation-analysis/` | `/sa` | SAPage, SAForm, SAOutput, QualityGate |
| Reports (L1772-L1795) | `features/reports/` | `/reports` | ReportsPage, ReportList, ReportPreview, ReportExport |

**Component Count Estimate:** 60-80 components (vs current 2)

---

## 4. Implementation Phases

### Phase 1 â€” Foundation (Weeks 1-3)

**Goal:** Set up TypeScript, Shadcn/ui, React Router, basic layout structure.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 1.1 | Initialize new TypeScript + Vite project | `npm create vite@latest ui-rewrite -- --template react-ts` |
| 1.2 | Install Shadcn/ui + Tailwind | `npx shadcn@latest init`, 10 primitives installed |
| 1.3 | Set up React Router 7 | Routes for `/`, `/operations`, `/reports`, `/system`, `/sources` |
| 1.4 | Build layout shell | Header, Sidebar, Layout component with responsive breakpoints |
| 1.5 | Port KPI cards to `/` home | OverviewPage with 5 KPI cards from [L613-L630](../../ui/src/App.jsx#L613-L630) |
| 1.6 | Set up Vitest | 1 smoke test per route |

**Deliverable:** TypeScript app with 5 routes, basic navigation, 5 KPI cards on home page.

---

### Phase 2 â€” Data Layer (Weeks 4-5)

**Goal:** Implement TanStack Query, migrate API client, add Zustand stores.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 2.1 | Install TanStack Query | `QueryClientProvider` in App.tsx |
| 2.2 | Create `lib/api.ts` client | Type-safe API functions with Zod schemas |
| 2.3 | Migrate `fetchOverview` to `useOverview` hook | Custom hook returns `{ data, isLoading, error }` |
| 2.4 | Migrate `fetchReports` to `useReports` hook | Paginated results, infinite scroll ready |
| 2.5 | Create Zustand `formStore` | Centralize form state, localStorage persistence |
| 2.6 | Add React Query Devtools | Debug cache, refetch, stale time |

**Deliverable:** All API calls use TanStack Query, form state in Zustand, localStorage persistence.

---

### Phase 3 â€” Operations Module (Weeks 6-7)

**Goal:** Migrate Command Center to `/operations` route.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 3.1 | Build `features/operations/OperationsPage.tsx` | Renders collection form + action buttons |
| 3.2 | Extract `CountrySelect` component | Shadcn Select with country chips |
| 3.3 | Extract `HazardPicker` component | Multi-select chips for disaster types |
| 3.4 | Migrate "Run Cycle" action | Button triggers mutation, shows progress toast |
| 3.5 | Migrate "Write Report" action | Form validation with Zod, loading state |
| 3.6 | Migrate "Write SA" action | Collapsible SA parameters panel |
| 3.7 | Add error boundary to `/operations` | Graceful error UI with retry button |

**Deliverable:** Full Command Center migrated to `/operations`, all 4 action buttons working.

---

### Phase 4 â€” Reports Module (Weeks 8-9)

**Goal:** Build `/reports` route with list, preview, export, and workbench.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 4.1 | Build `features/reports/ReportsPage.tsx` | Report list with search, filter, pagination |
| 4.2 | Add `ReportPreview` component | Markdown rendering with syntax highlighting |
| 4.3 | Add report export buttons | Download as PDF, DOCX, JSON |
| 4.4 | Migrate Workbench to `/workbench` tab | Side-by-side AI vs Deterministic comparison |
| 4.5 | Add preset management | Save/load workbench profiles with modal UI |
| 4.6 | Virtualize report list | React Virtuoso for 1000+ reports |

**Deliverable:** `/reports` route with full workbench, export, and virtualized list.

---

### Phase 5 â€” Sources & System (Weeks 10-11)

**Goal:** Build `/sources` and `/system` routes.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 5.1 | Build `features/sources/SourcesPage.tsx` | Source health table with freshness indicators |
| 5.2 | Add `ConnectorDiagnostics` component | Collapsible connector cards from [L1357](../../ui/src/App.jsx#L1357) |
| 5.3 | Add freshness trend chart | Recharts line chart showing stale/fresh over time |
| 5.4 | Build `features/system/SystemHealthPage.tsx` | Hardening panel, conformance, E2E summary |
| 5.5 | Add `FeatureFlagsPanel` | Toggle feature flags with API update |
| 5.6 | Add security baseline card | Display Moltis security check status |

**Deliverable:** `/sources` and `/system` routes with full diagnostics and health views.

---

### Phase 6 â€” Situation Analysis (Weeks 12-13)

**Goal:** Build `/sa` route with quality gate visualization.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 6.1 | Build `features/situation-analysis/SAPage.tsx` | SA form + output display |
| 6.2 | Add `SAQualityGate` component | 6-dimension bar chart from [L1730](../../ui/src/App.jsx#L1730) |
| 6.3 | Add SA markdown preview | Syntax-highlighted markdown with section anchors |
| 6.4 | Add SA export options | PDF, DOCX, HTML export |
| 6.5 | Add SA template selector | Load custom templates, show limits/usage |
| 6.6 | Add SA quality gate toggle | Conditional rendering based on `use_llm` flag |

**Deliverable:** `/sa` route with quality gate, templates, export, full SA workflow.

---

### Phase 7 â€” Backend Rewrite (Weeks 14-16)

**Goal:** Replace ThreadingHTTPServer with FastAPI + direct imports + caching.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 7.1 | Initialize FastAPI project | `src/api/main.py` with `/api/v1` prefix |
| 7.2 | Implement OpenAPI schema | Auto-generated docs at `/docs` |
| 7.3 | Replace subprocess calls | Direct Python imports from `agent_hum_crawler` |
| 7.4 | Add Redis caching | Cache overview for 60s, source-check for 5min |
| 7.5 | Add JWT authentication | Login endpoint, protected routes, token refresh |
| 7.6 | Add SSE endpoint for real-time updates | `/api/v1/events` stream for cycle progress |
| 7.7 | Deploy with Uvicorn + Docker | Dockerfile, docker-compose.yml, NGINX reverse proxy |

**Deliverable:** FastAPI backend with 10-50x lower latency, caching, auth, SSE.

---

### Phase 8 â€” Real-time Updates (Weeks 17-18)

**Goal:** Implement SSE-based live updates for cycle/report progress.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 8.1 | Add SSE client in frontend | `useSSE` hook connects to `/api/v1/events` |
| 8.2 | Add progress toasts | Real-time cycle progress (evidence â†’ ontology â†’ report) |
| 8.3 | Add live source health updates | Auto-refresh source table when new checks run |
| 8.4 | Add optimistic UI updates | Mutate cache before API response for instant feedback |
| 8.5 | Add notification center | Toast queue with dismiss, undo, history |
| 8.6 | Add reconnect logic | Auto-reconnect SSE on disconnect |

**Deliverable:** Real-time progress updates, no polling, live notifications.

---

### Phase 9 - Analysis-Driven Intelligence & Observability (Weeks 19-21)
**Goal:** Execute March 2026 validated analysis findings with implementation traceability from roadmap task -> analysis ID -> code/tests.
**Primary implementation reference:**
- [Deep Analysis - March 2026](../analysis/moltis_deep_analysis_march2026.md)
- [MarkItDown Repository](https://github.com/microsoft/markitdown)
**Developer rule (required):**
- Every Phase 9 PR must cite one or more analysis IDs in PR description/test notes (R22-R29, R16-R18, R13-R15).
| # | Workstream | Detailed Tasks | Acceptance Criteria | Analysis Reference |
|---|------------|----------------|---------------------|--------------------|
| 9.1 | ReliefWeb fields + narrative merge | Expand ReliefWeb fields (headline.title, headline.summary, file.mimetype, file.filename, file.description, origin) and implement deterministic text merge precedence | Connector persists richer report metadata with no regression in fetch stability | R22, R23 | ✅ Done 2026-03-04 |
| 9.2 | MIME-first attachment parsing with MarkItDown | Parse attachments by MIME first, extension fallback second; download full attachment bytes, then run MarkItDown (`markitdown[pdf,docx,xlsx]`) as primary converter with fallback extractors | Attachment parse coverage increases; unsupported types are explicitly tracked as skipped; PDF parse success target >=90% with `char_count >= 500` | R24, R25 | ✅ Done 2026-03-04 |
| 9.3 | Extraction telemetry model | Persist extraction diagnostics (`downloaded`, `status`, `method`, `char_count`, `duration_ms`, `error`) per attachment/document | Backend exposes reliable per-cycle extraction quality telemetry and method lineage (`markitdown` vs fallback) | R26 | ✅ Done 2026-03-04 |
| 9.4 | Diagnostics API + CLI | Add extraction diagnostics endpoint and CLI (extraction-report) for operators | Operators can identify top parser failures and low-yield sources in one query/command | R27, R28 | ✅ Done 2026-03-04 |
| 9.5 | Phoenix diagnostics UI | Add Sources/System diagnostics panel for extraction success rate, format mix, top errors, trend lines | UI provides actionable extraction health and regression visibility | R29 | ✅ Done 2026-03-05 |
| 9.6 | API/job observability | Add adaptive polling/backoff and surface job stage timings in UI | Reduced polling load and better operator visibility of long-running jobs | R16, R18 | ✅ Done 2026-03-05 |
| 9.7 | Orchestration consolidation | Route long workflows through shared coordinator/service contracts; enforce queue policy for heavy jobs | Reduced duplicated orchestration logic; predictable concurrency behavior | R13, R14, R15 | ✅ Done 2026-03-05 |
| 9.8 | Security baseline semantics | Refine `security-baseline-card.tsx` state mapping: promote combined hardening-fail + E2E-fail to explicit `critical` state; add tooltip text explaining pass/warn/fail reason | Combined failure is never silently downgraded to `warn`; tooltip renders for all three states | R17 | ✅ Done 2026-03-05 |
| 9.9 | Rust/Python NLP alignment | (1) Add `classify_all_impact_types(text) → Vec<String>` to `rust_core/src/text_classify.rs` (multi-label, matching Python's contract); expose via PyO3 + `rust_accel.py`. (2) Remove the blended workaround in `graph_ontology.py` — Rust path uses the new multi-label function directly. (3) Add drift-guard pytest that runs every NLP function (impact, need, severity, risk, figures) on 20 fixed sentences and asserts Rust == Python output. (4) Extract keyword tables to `config/nlp_keywords.toml`; `build.rs` codegen step generates Rust constants and Python dict from the single source. | `TestMultiImpact` passes natively via Rust with no Python supplement; drift-guard catches any future keyword-set divergence; zero duplicate keyword definitions in source tree | — | ✅ Done 2026-03-06 |
**Developer checklist:**
1. Link roadmap task and analysis IDs in code/PR.
2. Add or update tests for connector/API/UI contract changes.
3. Add diagnostics fields/events for behavior changes.
4. Update docs with implemented analysis references.
**Deliverable:** Production-ready extraction intelligence + monitoring layer with analysis-linked developer workflow.

---

### Phase 10 — Testing & Release (Weeks 22-24) 🔜 **NEXT — Starting 2026-03-06**

**Goal:** Close release-quality gaps, prove frontend/backend contract correctness, and establish objective production-readiness gates.

| # | Task | Acceptance Criteria | Status |
|---|------|-------------------|--------|
| 10.1 | Write unit tests | Coverage thresholds enforced in CI; current API client, query key, store, and Phase 5 suites remain green | In progress - coverage infrastructure and initial suites landed 2026-03-07 |
| 10.2 | Write integration tests | Test feature workflows (run cycle → view report) and API/UI contract paths for diagnostics, jobs, and system views | Not started |
| 10.3 | Add Playwright E2E tests | Full user journeys (5-10 scenarios) | Not started |
| 10.4 | Performance audit | Lighthouse score 90+, LCP < 2.5s, no route-level bundle regression beyond agreed thresholds | Not started |
| 10.5 | Accessibility audit | WCAG 2.1 AA compliance, keyboard nav, visible focus, semantic landmarks, and accessible labels on critical actions | Not started |
| 10.6 | Production deployment | Deploy to staging, then production with CI/CD | Not started |

**Deliverable:** Fully tested, performant, accessible app deployed to production.

---

### Phase 10A - Review-Driven Remediation (Added 2026-03-07)

**Goal:** Resolve gaps found in the whole-app review before the Phoenix roadmap can be considered release-ready.

| # | Workstream | Detailed Tasks | Acceptance Criteria | Status |
|---|------------|----------------|---------------------|--------|
| 10A.1 | API contract reconciliation | Align backend DB routes, frontend API client, and tests for extraction diagnostics; remove stale assumptions about available endpoints | `ui-phoenix/src/lib/api.ts`, tests, and FastAPI routes agree on every `/api/db/*` endpoint; extraction diagnostics path works end-to-end against a live server | Planned |
| 10A.2 | Feature flag data-shape safety | Replace boolean coercion of non-boolean config values with typed rendering/edit behavior; ensure unknown flag value types are not silently mutated | Non-boolean values such as `"false"`, `"0"`, or `"v2"` are displayed without being converted to enabled toggles; unit tests cover boolean, string, numeric, and unsupported values | Planned |
| 10A.3 | Real job identity and SSE ownership | Thread backend `job_id` through mutation lifecycle, stop using UI-local ids as surrogate jobs, and make SSE/polling state derive from backend job state | Every long-running mutation stores and surfaces the real backend `job_id`; global badge and toasts reflect backend status, not local placeholders | Planned |
| 10A.4 | Async UX deduplication | Remove duplicate toast/success handling between feature pages and mutation hooks; define one ownership layer for optimistic UX vs terminal status | One user action emits one success/error outcome; no duplicate success/error toasts in sources, reports, operations, or SA flows | Planned |
| 10A.5 | Coverage closure for Phase 5-10 UI | Add targeted tests for diagnostics panel, job stream behavior, system/settings edge cases, and route-level rendering failures | New tests cover every reviewed regression area; no roadmap item closes without a failing-first or contract test proving the defect | Planned |
| 10A.6 | Roadmap/code status reconciliation | Align roadmap narrative with shipped state: Phase 9 marked complete, Phase 10.1 reflected as in progress/delivered infrastructure, remove stale planned language | Roadmap, `progress.md`, and active UI test counts no longer contradict each other | Planned |

**Exit Criteria for Phase 10A:**

- Zero known Phoenix/frontend contract mismatches remain between roadmap and code.
- Zero duplicate toast/report-completion notifications remain in reviewed feature paths.
- All reviewed defects have either shipped fixes with tests or an explicitly deferred decision recorded in roadmap notes.

---

## 5. Migration Strategy

### 5.1 Parallel Development

**Approach:** Build new frontend alongside old dashboard, cut over when feature-complete.

- **Old Dashboard:** Keep running at `/dashboard` (1795-line App.jsx)
- **New Frontend:** Develop at `/v2` or subdomain `app.agent-hum-crawler.local`
- **API Migration:** FastAPI backend supports both old and new clients
- **Cutover:** When Phase 10 complete, switch default route to new frontend

**Benefits:**
- No risk of breaking existing workflows
- Side-by-side comparison during development
- Gradual user adoption with opt-in beta access

---

### 5.2 Data Migration

**No database migration required** â€” all data remains in SQLite + filesystem (reports/).

**API Contract Changes:**
- FastAPI endpoints use RESTful conventions (`/api/v1/cycles`, `/api/v1/reports/{id}`)
- Backward-compatible shim layer for old dashboard during transition
- OpenAPI schema ensures type safety across frontend/backend boundary

---

### 5.3 User Training

| Audience | Materials | Timeline |
|----------|-----------|----------|
| **Internal Devs** | Architecture docs, component storybook, API docs | Week 1 (Phase 1 start) |
| **Power Users** | Video walkthrough, keyboard shortcuts guide | Week 20 (Phase 9 complete) |
| **All Users** | Migration announcement, comparison guide, support chat | Week 24 (Phase 10 cutover) |

---

## 6. Success Metrics

### 6.1 Delivery Targets

| Metric | Baseline on 2026-03-07 | Release Target | Measurement |
|--------|-------------------------|----------------|-------------|
| **Route coverage** | Primary Phoenix routes implemented | 100% route smoke coverage in CI | Vitest integration/smoke suite |
| **Frontend unit coverage** | Coverage infrastructure landed | >= 80% statements, >= 75% branches, >= 80% functions, >= 80% lines | `@vitest/coverage-v8` CI report |
| **Contract coverage** | Partial (`api-client`, query keys, stores) | Every `/api/*` route used by Phoenix has a client/schema/test contract | API contract tests |
| **Type safety** | 0 TypeScript errors reported in progress | Keep `tsc --noEmit` at zero | CI typecheck |
| **Open critical defects** | Multiple review findings remain | 0 critical / 0 high before cutover | QA defect tracker |

### 6.2 Performance Targets

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| **Initial Load Time** | 1-2s | < 1.5s | Lighthouse LCP |
| **Time to Interactive** | 2-3s | < 2s | Lighthouse TTI |
| **API Response Time** | 5-30s | < 500ms | 95th percentile (cached) |
| **Bundle Size** | 250KB | < 400KB | Gzipped main bundle |
| **Concurrent Users** | 1-5 | 100+ | Load test (Locust) |

### 6.3 Developer Experience Targets

| Metric | Current | Target |
|--------|---------|--------|
| **Component Count** | 2 | 60-80 |
| **Lines per File** | 1795 max | 150 avg, 300 max |
| **Test Coverage** | Coverage infrastructure in progress | 80%+ with CI enforcement |
| **Type Safety** | 0% (JS) | 100% (TS strict) |
| **Build Time** | 2-3s | < 5s |
| **Onboarding Time** | 3-5 days | 1 day |

### 6.4 User Experience Targets

| Feature | Current | Target |
|---------|---------|--------|
| **Navigation** | Vertical scroll | Tab-based routing |
| **Real-time Updates** | Mixed polling/SSE behavior | Real backend job state shown consistently across views |
| **Search** | None | Fuzzy search across all entities |
| **Data Export** | None | PDF, DOCX, JSON, CSV |
| **Accessibility** | WCAG Fail | WCAG 2.1 AA |
| **Mobile Support** | Broken | Responsive (768px+) |

### 6.5 QA Acceptance Gate

No Phoenix phase or remediation item is complete until all of the following are attached to the work item or PR:

1. Test evidence: updated unit, integration, or E2E results for the touched path.
2. Contract evidence: if API behavior changed, client schema, route, and tests are updated together.
3. Regression note: explicit statement of what reviewed defect or risk was addressed.
4. Manual QA note: route exercised in local or staging environment with observed result.
5. Documentation sync: roadmap, progress, and relevant docs updated if status or behavior changed.

### 6.6 QA Review Protocol

For implementation starting from this roadmap revision, QA review uses this bar:

- Block closure if acceptance criteria are vague or not measurable.
- Block closure if test evidence does not cover the reviewed regression.
- Block closure if frontend/backend behavior differs from roadmap claims.
- Re-open work if a defect is marked fixed in docs or UI copy while runtime behavior is unchanged.

---

## 7. Risk Assessment

### 7.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Backend rewrite delays** | Medium | High | Phase 7 can run in parallel with Phases 1-6 |
| **FastAPI migration breaks old dashboard** | Low | High | Shim layer + comprehensive API tests |
| **Component library issues** | Low | Medium | Shadcn/ui is copy-paste, can swap components |
| **TypeScript migration errors** | Medium | Medium | Strict mode opt-in, gradual type coverage |
| **SSE connectivity issues** | Medium | Medium | Polling fallback, reconnect logic |

### 7.2 Resource Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **6-month timeline too aggressive** | High | High | Phased approach allows MVP at Phase 6 (13 weeks) |
| **1-2 devs insufficient** | Medium | High | Prioritize Phases 1-6, defer Phases 7-10 |
| **Context switching slows progress** | High | Medium | Dedicated sprint blocks for frontend work |

### 7.3 User Adoption Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Users prefer old dashboard** | Low | Medium | Parallel deployment, opt-in beta, feedback loop |
| **Missing features at cutover** | Medium | High | Feature parity checklist, user testing |
| **Training materials insufficient** | Medium | Low | Video walkthroughs, in-app tooltips |

---

## 8. Cost Estimation

### 8.1 Development Effort

| Phase | Weeks | FTE (devs) | Total Dev-Weeks |
|-------|-------|------------|-----------------|
| Phase 1 â€” Foundation | 3 | 1 | 3 |
| Phase 2 â€” Data Layer | 2 | 1 | 2 |
| Phase 3 â€” Operations | 2 | 1 | 2 |
| Phase 4 â€” Reports | 2 | 1 | 2 |
| Phase 5 â€” Sources/System | 2 | 1 | 2 |
| Phase 6 â€” Situation Analysis | 2 | 1 | 2 |
| Phase 7 â€” Backend Rewrite | 3 | 1-2 | 4 |
| Phase 8 â€” Real-time | 2 | 1 | 2 |
| Phase 9 - Analysis-Driven Intelligence & Observability | 3 | 1 | 3 |
| Phase 10 â€” Testing/Release | 3 | 1-2 | 4 |
| **Total** | **24 weeks** | **1-2** | **26 dev-weeks** |

**Calendar Time:**
- **1 developer:** 6 months (26 weeks)
- **2 developers:** 3.5-4 months (parallel Phases 1-6 + 7)
- **3 developers:** 2.5-3 months (Phase 1-6 + Phase 7 + Phase 9 in parallel)

### 8.2 Infrastructure Costs (Annual)

| Service | Cost | Purpose |
|---------|------|---------|
| **Staging Environment** | $50/mo | Development testing |
| **Production Hosting** | $200/mo | 4-core, 8GB RAM, 100GB storage |
| **Redis Cache** | $30/mo | Managed Redis (1GB) |
| **Monitoring (Grafana Cloud)** | $50/mo | Metrics, logs, alerts |
| **Domain + SSL** | $20/yr | HTTPS certificate |
| **Total Annual** | **$3,980** | Assuming 100+ concurrent users |

---

## 9. Alternatives Considered

### 9.1 Incremental Refactor

**Approach:** Gradually decompose App.jsx into smaller components while keeping existing architecture.

**Pros:** Lower risk, no rewrite overhead, incremental delivery  
**Cons:** Cannot fix foundational issues (no routing, data layer, state management), 6-12 month timeline similar to rewrite without architectural benefits

**Decision:** **Rejected** â€” Technical debt too deep for incremental approach.

---

### 9.2 Low-Code Platform (Retool, Appsmith)

**Approach:** Use drag-and-drop UI builder to replace custom frontend.

**Pros:** 50-75% faster development, built-in components, auth, data connectors  
**Cons:** Vendor lock-in, limited customization, poor TypeScript support, cannot self-host Retool

**Decision:** **Rejected** â€” Too constrained for humanitarian intelligence platform.

---

### 9.3 Framework Switch (Next.js, SvelteKit)

**Approach:** Rewrite in Next.js for SSR, file-based routing, server actions.

**Pros:** SEO-friendly, better performance, RSC, API routes  
**Cons:** Additional learning curve, overkill for internal dashboard, no SEO requirement

**Decision:** **Deferred** â€” Stick with React + Vite for team familiarity. Reassess if public-facing frontend needed.

---

## 10. Next Steps

### Immediate Actions (This Week)

1. **Get buy-in:** Present this roadmap to stakeholders
2. **Assign resources:** Allocate 1-2 developers for 6-month sprint
3. **Set up project:** Create `ui-rewrite/` directory or new repo
4. **Phase 1 kickoff:** Initialize TypeScript + Shadcn/ui + React Router

### First Milestone (3 Weeks)

- **Deliverable:** TypeScript app with 5 routes, basic navigation, 5 KPI cards on home page (Phase 1 complete)
- **Demo:** Live preview of `/` home route with KPIs
- **Decision Point:** Proceed to Phase 2 or adjust timeline

---

## References

| Document | Purpose |
|----------|---------|
| [Frontend Audit Report](../analysis/frontend-audit-report.md) | Root cause analysis of current dashboard issues |
| [Project Clarity Roadmap](project-clarity-roadmap.md) | Backend intelligence layer roadmap |
| [Current Dashboard](../../ui/src/App.jsx) | 1795-line monolithic component to replace |
| [Dashboard API](../../scripts/dashboard_api.py) | Current Python API server |

---

**Approval Required:** Stakeholder sign-off on 6-month timeline and resource allocation.

**Contact:** Project lead for questions or alternative proposals.



# Progress Tracker - Dynamic Disaster Intelligence Assistant

Date: 2026-02-20
Last Updated: 2026-02-21
Status: Post-MVP Hardening + **Project Clarity** (Phase 3 Expansion Complete)

## Overall Progress
- Documentation and specification phase: 100% complete
- MVP implementation phase: 100% complete
- Post-MVP hardening and operator tooling: in active rollout
- Humanitarian ontology and Situation Analysis engine: implemented and validated
- Graph ontology evidence extraction: operational with multi-pattern NLP

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
- Current test status: `187 passed`.
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
4. Continue security/auth hardening rollout from `specs/13-moltis-security-auth.md`.
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

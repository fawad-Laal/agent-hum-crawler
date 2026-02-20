# Frontend Roadmap - Agent HUM Crawler Dashboard

Date: 2026-02-20  
Status: Active (Phase 2 advanced, Phase 3 started)

## Purpose
Define a focused frontend roadmap for the custom operator interface that monitors crawler quality, report quality, and agent behavior improvements.

## Scope
- React dashboard in `ui/`
- Local API bridge in `scripts/dashboard_api.py`
- Quality/health/report observability for fast iteration

## Principles
- Keep frontend tightly coupled to measurable backend outputs.
- Prefer deterministic metrics and gate states over subjective UI signals.
- Ship incrementally with each phase tied to operational decisions.

## Phase 0 - Baseline (Completed)
Delivered:
- Minimal React UI scaffold (Vite + React).
- Run cycle action (`run-cycle`) from UI.
- Report generation action (`write-report`) from UI.
- KPI snapshot panel (`quality-report`, `source-health`, `hardening-gate`).
- Report list and markdown preview.
- Template selection (`brief`, `detailed`, `default`) and optional LLM toggle.

Evidence:
- `ui/` created and integrated with local API proxy.
- `scripts/dashboard_api.py` exposes dashboard endpoints.

## Phase 1 - Operator Monitoring (In Progress)
Goal:
Make quality regressions obvious within one screen.

Work items:
1. Add trend charts for:
   - duplicate rate estimate
   - traceable rate
   - connector failure rate
   - LLM enrichment rate
2. Add hardening gate panel with threshold vs actual values.
3. Add conformance panel (streaming/tool registry/MCP/auth-proxy checks).
4. Add source-health table with failure hotspots and recovered status.

Acceptance:
- Operator can identify top 3 degradations in less than 2 minutes.

Current implementation status:
- Added trend charts in UI for:
  - cycle events
  - LLM enriched/fallback/validation failures
  - rolling quality rates (duplicate, traceable, LLM enrichment, citation coverage)
- Added hardening threshold panel (actual vs threshold with check status).
- Added conformance/security snapshot from latest E2E summary artifacts.
- Added source-health hotspot table ranked by failure rate.
- API upgraded to provide:
  - cycle history (`show-cycles`)
  - rolling quality trend snapshots
  - latest E2E summary context

## Phase 2 - Report Quality Workbench (In Progress)
Goal:
Improve long-form report quality through structured diagnostics.

Work items:
1. Show report quality metrics inline:
   - citation density
   - missing sections
   - invalid citation refs
   - unsupported claims
2. Add side-by-side report compare view (deterministic vs AI-assisted).
3. Add per-section token/length budget indicators from templates.
4. Add one-click rerun with same filter/template profile.

Acceptance:
- Failed report quality gates are explainable without leaving the UI.

Current implementation status:
- Added one-click report workbench compare flow:
  - deterministic run
  - AI-assisted run
- Added side-by-side quality diagnostics:
  - status
  - citation density
  - word count
  - missing sections
  - unsupported incident blocks
  - invalid citation refs
- Added section budget usage table from template section titles/limits.
- Added side-by-side markdown preview panel (deterministic vs AI).
- API endpoint added: `POST /api/report-workbench` in `scripts/dashboard_api.py`.
- Added reusable compare presets and one-click repeatability:
  - persisted preset store (`config/dashboard_workbench_profiles.json`)
  - UI preset save/load/delete controls
  - one-click `Rerun Last Profile` action
  - API endpoints:
    - `GET /api/workbench-profiles`
    - `POST /api/workbench-profiles/save`
    - `POST /api/workbench-profiles/delete`
    - `POST /api/report-workbench/rerun-last`
- Added operator feedback and input robustness refinements:
  - explicit last-action status indicator (success/fail) above raw output payload,
  - clearer in-flight action labels for run/report buttons,
  - disaster-type alias normalization support in backend path used by UI (`Floods`, `Cyclones`, etc.).
- Added explicit data recency + source audit controls:
  - `max_age_days` control wired to cycle and report runs (filters stale items/events),
  - one-click `Source Check` action in UI and API (`POST /api/source-check`),
  - per-source verification table (connector, status, fetched, matched, working).
- Added centralized runtime flag visibility:
  - `feature_flags` now exposed in dashboard overview,
  - UI `Feature Flags` panel for operator awareness of active toggles.
- Added explainability + freshness diagnostics in Per-Source Check:
  - freshness status badge (`fresh` / `stale` / `unknown`) with age-in-days,
  - stale action visibility (`warn` / `demote`) from backend stale-policy state,
  - match-reason diagnostics per source (`country_miss`, `hazard_miss`, `age_filtered`),
  - source-check summary now includes stale/demoted source counts.
- Added retrieval tuning controls for report relevance:
  - `Country Min Events` (cross-country balance floor),
  - `Max / Connector` cap,
  - `Max / Source` cap,
  - wired through dashboard API into write-report and workbench compare runs.

## Phase 3 - Agent Improvement Console
Goal:
Turn dashboard into a concrete optimization loop for crawler/agent behavior.

Work items:
1. Cycle replay trigger and outcome diff (event added/changed/suppressed).
2. Connector-level diagnostics:
   - latency
   - parse failures
   - dedupe suppression impact
3. LLM enrichment diagnostics:
   - provider errors
   - validation failures
   - fallback frequency
4. Improvement suggestions module (rule-based):
   - weak sources
   - low diversity windows
   - high duplicate windows

Acceptance:
- UI can explain why quality dropped and what to tune next.

Current implementation status:
- Started per-source explainability and operational diagnostics:
  - source freshness badges (`fresh` / `stale` / `unknown`),
  - stale action surfacing (`warn` / `demote`),
  - match-reason diagnostics (`country_miss`, `hazard_miss`, `age_filtered`).
- Added retrieval tuning controls for better report relevance:
  - country-balance floor (`Country Min Events`),
  - max-per-connector and max-per-source caps in report/workbench flows.

## Phase 4 - Multi-Session Operations
Goal:
Support real operations workflow with repeatable runs and auditability.

Work items:
1. Saved dashboard profiles (country/disaster/template presets).
2. Run history with artifact links (`artifacts/e2e/<timestamp>/`).
3. Role-oriented views:
   - analyst (detailed quality/debug)
   - donor/briefing (summary-first)
4. Export views:
   - report package (markdown + JSON metrics)
   - incident monitoring snapshot

Acceptance:
- Team can run repeatable analysis sessions with shared presets.

## Technical Milestones
1. API hardening:
   - typed endpoint contracts
   - explicit command timeout handling
   - error normalization
2. Frontend quality:
   - componentized layout
   - loading/error states for each panel
   - test coverage for critical interactions
3. Release integration:
   - frontend smoke in local validation/E2E gate
   - build artifact checks

## Risks
- CLI command latency can degrade UX if no async progress model is added.
- LLM-dependent actions can create inconsistent user expectations if fallback states are not explicit.
- UI complexity may outrun metric quality unless backend diagnostics remain first-class.

## Success Metrics
- Time-to-diagnose quality drop < 2 minutes.
- Report rework cycles reduced by >30%.
- Conformance/hardening regressions detected in UI before release gate failures.

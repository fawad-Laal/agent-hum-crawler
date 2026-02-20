# Progress Tracker - Dynamic Disaster Intelligence Assistant

Date: 2026-02-20
Last Updated: 2026-02-20
Status: Post-MVP Hardening + Frontend Operator Console In Progress

## Overall Progress
- Documentation and specification phase: 100% complete
- MVP implementation phase: 100% complete
- Post-MVP hardening and operator tooling: in active rollout

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
- Current test status: `46 passed`.

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

## Next Action Queue
1. Continue security/auth hardening rollout from `specs/13-moltis-security-auth.md`:
   - add runtime auth-path probes (local/remote/proxy simulation) for direct behavioral validation.
   - add optional strict requirement for at least one non-admin scoped automation key in production profiles.
2. Continue implementation of `specs/15-llm-intelligence-layer-v1.md`:
   - tighten AI narrative conformance around section aliases and unsupported-claim checks in live windows.
   - improve source ranking/selection quality for cross-country filter balance in sparse windows.
3. Continue streaming/tool-registry conformance rollout from `specs/14-moltis-streaming-tool-registry.md`.
4. Continue frontend roadmap execution (`specs/frontend-roadmap.md`):
   - complete Phase 3 diagnostics (connector latency/error classes, outcome diff views),
   - add operator run-history with artifact linking for repeatable QA loops.

## Risks / Blockers
- No blocking issues for MVP sign-off.

## References
- `specs/05-roadmap.md`
- `specs/09-stocktake.md`
- `specs/10-pilot-signoff.md`

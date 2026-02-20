# Development Roadmap - Dynamic Disaster Intelligence Assistant

Date: 2026-02-20
Version: 1.2

## Roadmap Goals
- Deliver MVP with dynamic user-defined monitoring filters.
- Ensure alert quality (verification, low duplicates, calibrated severity/confidence).
- Reach stable scheduled operation in Moltis chat.

## Timeline Overview (6 Weeks)
- Week 1: Foundation and configuration intake
- Week 2: Monitoring pipeline and normalization
- Week 3: Intelligence logic (dedupe + calibration)
- Week 4: Scheduling, persistence, and operationalization
- Week 5: Testing, replay validation, and hardening
- Week 6: Pilot run, tuning, and MVP sign-off

## Milestones

### Milestone 1 (End of Week 1): Configurable Agent Foundation
Status: Completed

### Milestone 2 (End of Week 2): Monitoring Engine v1
Status: Completed

### Milestone 3 (End of Week 3): Alert Intelligence v1
Status: Completed

### Milestone 4 (End of Week 4): Operational Alert Delivery
Status: Completed

### Milestone 5 (End of Week 5): QA and Hardening
Status: Completed

### Milestone 6 (End of Week 6): MVP Pilot and Sign-off
Status: Completed
Delivered so far:
- 7-cycle pilot executed.
- KPI snapshots captured (`quality-report`, `source-health`, `hardening-gate`).
- Automated pilot orchestration command added (`pilot-run`) to produce sign-off evidence in one run.
Final sign-off evidence:
- `hardening-gate`: `pass`
- `llm-report --enforce-llm-quality`: `pass`
- `conformance-report`: `pass`

## Immediate Next Actions
1. Expand country gazetteers (Ethiopia, DRC, Sudan, Somalia).
2. Implement full-article fetching for richer NLP extraction.
3. Add forecast/risk extraction (FEWS NET IPC phases, ECMWF cyclone tracks).
4. Persist ontology graph to SQLite for cross-cycle trend analysis.
5. Complete streaming/tool-registry conformance (item 6 below).
6. Continue source expansion and production readiness.

## Post-MVP Hardening Track
After Milestone 6 sign-off, execute `specs/12-moltis-advanced-operations.md` in this order:
1. Hook safety and audit controls. Status: Completed.
Evidence:
- Startup registration includes shell hooks: `ahc-audit-log`, `ahc-llm-tool-guard`, `ahc-tool-safety-guard`.
- Moltis log line: `7 hook(s) discovered (4 shell, 3 built-in), 6 registered`.
- Guard hooks block known-dangerous test payloads; audit hook writes JSONL records.
2. Hardened Moltis configuration profile rollout. Status: Completed.
Evidence:
- Hardened profile template created: `config/moltis.hardened.example.toml`.
- Includes sandbox/network hardening, browser domain restrictions, hooks, metrics, and memory settings.
- Rollout instructions documented in `README.md`.
3. Skill self-extension governance and session branching SOP. Status: Baseline implemented.
Evidence:
- Governance/SOP documented in `specs/16-phase-c-skill-branch-sop.md`.
- `delete_skill` explicit-confirmation policy enforced in hook policy layer.
- Tests added to guard against unconfirmed skill deletion.
4. Local-validation and e2e release gates. Status: Baseline implemented.
Evidence:
- `scripts/local-validate.ps1` and `scripts/local-validate.sh` added.
- README includes local gate execution commands.
- Gate now runs deterministic test + compile checks for release readiness.
- Added full deterministic E2E gate with artifact capture (`scripts/e2e_gate.py`).
- E2E evidence outputs are stored in `artifacts/e2e/<UTC timestamp>/`.
5. Security/auth hardening rollout from `specs/13-moltis-security-auth.md` (auth matrix, proxy posture, scoped keys, third-party skills trust controls).
Status: In progress.
Evidence:
- Added automated baseline verifier: `scripts/moltis_security_check.py`.
- Live config validation pass captured against local Moltis runtime config:
  - `auth.disabled=false`
  - `tools.exec.approval_mode=on-miss`
  - `tools.exec.sandbox.mode=all`
  - `metrics.enabled=true`
  - `metrics.prometheus_endpoint=true`
  - hooks present (`>=1`)
- Added auth/proxy matrix evidence output:
  - scenario evidence for local/remote credentialed and no-credential modes
  - proxy expectation checks with `--expect-behind-proxy true|false|auto`
- Added scoped API-key verification checks:
  - active keys required (optional strict mode)
  - unscoped active keys fail
  - unknown scope values fail
  - `operator.admin` usage surfaced as warning telemetry
- Wired security checks into deterministic E2E gate:
  - artifact: `06_moltis_security_check.json`
  - summary includes `security_status`
  - latest run: `status=pass`
6. Streaming/tool-registry conformance from `specs/14-moltis-streaming-tool-registry.md` (event lifecycle, websocket UX, MCP source filtering).
7. LLM Intelligence Layer v1 from `specs/15-llm-intelligence-layer-v1.md` (full-text extraction/summary, LLM severity-confidence calibration, citation-locked outputs, deterministic fallback).
Status: In progress (GraphRAG report layer + report quality gates + Humanitarian Ontology & Situation Analysis implemented).
Evidence:
- Added GraphRAG report pipeline (`write-report`) over SQLite evidence.
- Added report quality gates (citation density, section completeness, unsupported-claim checks).
- Enforced report quality in E2E gate (`scripts/e2e_gate.py`).
- Latest deterministic E2E run includes `report_quality_status=pass`.
- Added template-driven report rendering with editable section and length controls:
  - `config/report_template.json` (default),
  - `config/report_template.brief.json`,
  - `config/report_template.detailed.json`.
- Added `write-report --report-template` for profile selection and format standardization.
- AI drafting integration hardened:
  - `.env` loading for report command,
  - robust OpenAI Responses parsing (structured `output` support),
  - explicit `AI Assisted: Yes` banner on true AI-generated outputs.
- Citation format standardized across AI/deterministic outputs:
  - numbered in-text citation refs and numbered end citation list.
- Added minimal operator UI baseline for rapid quality iteration:
  - local API bridge (`scripts/dashboard_api.py`) wrapping existing CLI commands
  - React dashboard scaffold (`ui/`) for run-cycle, write-report, KPI snapshot, and report preview
- Source integration quality improvements:
  - ReliefWeb connector upgraded to API v2 with filter-aware query payload.
  - GDACS upgraded to hazard-specific 7-day feeds (all/flood/cyclone).
  - FEWS NET RSS feeds integrated for analysis and weather/agriculture outlook coverage.
- **Humanitarian Ontology Graph** (`graph_ontology.py`):
  - Typed ontology with hazard/impact/need/response/risk/admin-area nodes.
  - 4-pattern NLP figure extraction (deaths, displaced, affected, houses) with `max()` accumulation.
  - Built-in country gazetteers: Madagascar (22 provinces, 100+ districts), Mozambique (10 provinces, 50+ districts).
  - Auto-country detection from evidence for automatic gazetteer loading.
  - Admin1/Admin2 geo-detection against gazetteer entries.
  - 34 dedicated tests.
- **OCHA-Style Situation Analysis** (`situation_analysis.py`, `write-situation-analysis`):
  - Template-driven 15-section renderer: executive summary, national/admin impact tables, 6 sectoral analyses, access constraints, outstanding needs, forecast, admin reference annex, citations.
  - Event name auto-inference from evidence titles (proper noun regex).
  - Dynamic access constraint extraction from evidence body text.
  - Evidence-based sector narrative construction.
  - Dashboard API endpoint (`/api/write-situation-analysis`) with full parameter support.
  - SA generation form added to React frontend.
  - SA JSON template: `config/report_template.situation_analysis.json`.
  - 20 dedicated tests (54 new tests total including ontology).

## Post-MVP Track: Humanitarian Ontology & SA Quality
After LLM Intel Layer baseline, ongoing quality hardening for SA output:
1. **Country gazetteer expansion** — Add Ethiopia, DRC, Sudan, Somalia, Myanmar gazetteers for admin1/admin2 geo-detection.
2. **Full-article fetching** — Retrieve full article text from source URLs for richer NLP extraction (current evidence is RSS snippet-length, 85-168 chars).
3. **Forecast & risk extraction** — Parse IPC food-security phases from FEWS NET feeds; ingest ECMWF cyclone track data for risk outlook section.
4. **Ontology persistence** — Persist `HumanitarianOntologyGraph` to SQLite for cross-cycle trend analysis and delta reporting.
5. **LLM/deterministic balance** — Define clear LLM vs deterministic boundary for each SA section; add feature flag for per-section control.
6. **Sector coverage expansion** — Add Logistics/Telecoms, Nutrition, and Camp Coordination sectors from expanded source set.
7. **SA quality gate** — Automated quality scoring for SA outputs (figure coverage, sector fill rate, geographic specificity).

# Development Roadmap - Dynamic Disaster Intelligence Assistant

Date: 2026-02-18
Version: 1.1

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
1. Begin post-MVP hardening execution track.
2. Convert remaining manual evidence capture steps into automated scripts where feasible.
3. Continue source expansion and production readiness.

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
6. Streaming/tool-registry conformance from `specs/14-moltis-streaming-tool-registry.md` (event lifecycle, websocket UX, MCP source filtering).
7. LLM Intelligence Layer v1 from `specs/15-llm-intelligence-layer-v1.md` (full-text extraction/summary, LLM severity-confidence calibration, citation-locked outputs, deterministic fallback).
Status: In progress (GraphRAG report layer + report quality gates implemented).
Evidence:
- Added GraphRAG report pipeline (`write-report`) over SQLite evidence.
- Added report quality gates (citation density, section completeness, unsupported-claim checks).
- Enforced report quality in E2E gate (`scripts/e2e_gate.py`).
- Latest deterministic E2E run includes `report_quality_status=pass`.

# Development Roadmap - Dynamic Disaster Intelligence Assistant

Date: 2026-02-18
Version: 1.0

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
Status: In Progress
Delivered so far:
- 7-cycle pilot executed.
- KPI snapshots captured (`quality-report`, `source-health`, `hardening-gate`).
- Automated pilot orchestration command added (`pilot-run`) to produce sign-off evidence in one run.
Pending for final sign-off:
- reliefweb activation and re-pilot with richer event coverage
- NGO source stabilization
- hardening-gate status `pass` on non-zero event dataset (achieved)
- Moltis runtime alignment checks complete (prompt layering, streaming UX, metrics endpoints)
- Tool registry conformance checks complete (`source`/`mcpServer`, MCP-disable fallback)
- Auth/proxy matrix checks complete (local/remote/proxy behavior)
- LLM quality thresholds pass in 7-cycle enforced window (`llm_enrichment_rate_ok`, `citation_coverage_ok`) (achieved)

## Immediate Next Actions
1. Capture Moltis conformance evidence and set checks to `pass` where verified:
   - streaming lifecycle
   - tool registry source metadata
   - MCP-disabled builtin fallback
   - auth/proxy matrix
2. Run `conformance-report --limit 7 ...` with verified check statuses.
3. Publish final Milestone 6 sign-off snapshot in `specs/10-pilot-signoff.md`.

## Post-MVP Hardening Track
After Milestone 6 sign-off, execute `specs/12-moltis-advanced-operations.md` in this order:
1. Hook safety and audit controls.
2. Hardened Moltis configuration profile rollout.
3. Skill self-extension governance and session branching SOP.
4. Local-validation and e2e release gates.
5. Security/auth hardening rollout from `specs/13-moltis-security-auth.md` (auth matrix, proxy posture, scoped keys, third-party skills trust controls).
6. Streaming/tool-registry conformance from `specs/14-moltis-streaming-tool-registry.md` (event lifecycle, websocket UX, MCP source filtering).
7. LLM Intelligence Layer v1 from `specs/15-llm-intelligence-layer-v1.md` (full-text extraction/summary, LLM severity-confidence calibration, citation-locked outputs, deterministic fallback).

# MVP Backlog - Dynamic Disaster Monitoring Agent

Date: 2026-02-17

## Phase 1 - Foundation
1. Runtime config intake flow
- Task: implement prompt flow to collect required fields and confirm JSON.
- Acceptance: user can provide config once and start monitoring.

2. Config validation
- Task: validate countries, disaster types, interval range.
- Acceptance: invalid values trigger clear correction prompts.

3. State initialization
- Task: initialize state object with hashes and timestamps.
- Acceptance: first cycle runs without prior state errors.

## Phase 2 - Monitoring Engine
1. Source collection pipeline
- Task: fetch source updates using country/type filters.
- Acceptance: pipeline returns structured candidate items.

2. Event normalization
- Task: map candidates to standard event schema.
- Acceptance: each event has source URL + updated timestamp.

3. Classification
- Task: assign severity/confidence with documented rules.
- Acceptance: all events receive both labels.

## Phase 3 - Alert Intelligence
1. Deduplication and change detection
- Task: hash/fuzzy compare against previous cycle.
- Acceptance: unchanged items are suppressed correctly.

2. Alert routing (Moltis only)
- Task: emit high/critical always; medium on meaningful changes.
- Acceptance: routing rules match product spec exactly.

3. Output formatting
- Task: render concise alert format and batch summary.
- Acceptance: all alerts include severity, confidence, links, timestamp.

## Phase 4 - QA and Hardening
1. Dry-run replay tests
- Task: run against known historical events and verify output.
- Acceptance: duplicate and false alert rate within targets.

2. Failure-path tests
- Task: test provider down, partial source outage, malformed source item.
- Acceptance: cycle completes with graceful degradation.

3. Operational review
- Task: confirm logs/metrics for run health and alert counts.
- Acceptance: operator can audit any alert back to sources.

## Deliverables
- Dynamic prompt flow integrated
- Monitoring workflow active on interval
- Moltis chat alerts with traceable sources
- Documented runbook for daily operation

## Phase 5 - Moltis Native Operations Alignment
1. Prompt persona files and instruction layering
- Task: configure `~/.moltis/IDENTITY.md`, `SOUL.md`, and `USER.md` for this disaster-monitoring assistant.
- Acceptance: runtime sessions consistently load persona + project instructions without prompt bloat.

2. Streaming UX validation
- Task: validate streaming responses in multi-tool cycles (delta text + tool state events).
- Acceptance: long cycle runs provide incremental user feedback with no broken final message.

3. Observability integration
- Task: verify Moltis metrics endpoints and map key gateway metrics to app health KPIs.
- Acceptance: operator can diagnose LLM/tool/browser failures and correlate with connector failures.

## Phase 6 - Advanced Moltis Operations (Post-MVP Hardening)
1. Hook policy pack
- Task: implement and test `BeforeLLMCall`, `AfterLLMCall`, and `BeforeToolCall` hooks for injection/tool safety.
- Acceptance: known unsafe tool-call patterns are blocked in controlled tests.

2. Skill self-extension governance
- Task: define allow/deny policy for `create_skill`, `update_skill`, `delete_skill` and enforce deletion confirmation.
- Acceptance: skill modifications are auditable and safe by default.

3. Session branching SOP
- Task: define incident-branch workflow and merge-back summary pattern.
- Acceptance: at least one incident simulation uses branch workflow end-to-end.

4. Local validation + E2E gate
- Task: adopt local parity checks and browser e2e checks before release.
- Acceptance: release candidate includes passing validation evidence.

5. Auth and proxy hardening profile
- Task: define and validate auth gate behavior for local, remote, and proxied deployments.
- Acceptance: scoped API-key model and proxy classification controls are documented and tested.

6. Third-party skills trust controls
- Task: enforce trust/provenance/drift handling policy for external skill sources.
- Acceptance: untrusted or drifted skills cannot remain enabled without explicit re-trust.

7. Streaming and tool-registry conformance
- Task: validate streaming event flow and runner/gateway/websocket mappings for long tool-heavy cycles.
- Acceptance: deltas/tool lifecycle events are consistent and MCP source filtering behaves as expected.

8. LLM Intelligence Layer v1
- Task: implement optional LLM enrichment for full-text summary + severity/confidence calibration with strict citation locking.
- Acceptance: all LLM-enriched outputs include URL + quote spans; deterministic rules are used automatically when LLM is unavailable.

## Definition of Done (MVP)
- End-to-end operation for 7 consecutive cycles without blocking errors.
- Critical/high alerts emitted correctly during test scenarios.
- Duplicate alert suppression verified.
- User can update countries/disaster types/interval without code changes.

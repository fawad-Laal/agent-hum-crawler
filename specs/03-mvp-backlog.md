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

## Definition of Done (MVP)
- End-to-end operation for 7 consecutive cycles without blocking errors.
- Critical/high alerts emitted correctly during test scenarios.
- Duplicate alert suppression verified.
- User can update countries/disaster types/interval without code changes.

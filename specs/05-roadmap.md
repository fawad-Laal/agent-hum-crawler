# Development Roadmap - Dynamic Disaster Intelligence Assistant

Date: 2026-02-17
Version: 0.2

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
Delivered:
- Runtime intake flow
- Input validation (`countries`, `disaster_types`, `check_interval_minutes`)
- Initial state persistence

### Milestone 2 (End of Week 2): Monitoring Engine v1
Status: Completed
Delivered:
- Multi-source collection pipeline (ReliefWeb + government + UN + NGO + local news)
- Normalized source item model
- Country source allowlist registry

### Milestone 3 (End of Week 3): Alert Intelligence v1
Status: Completed
Delivered:
- Dedupe + change detection
- Multi-source corroboration scoring
- Severity/confidence calibration

### Milestone 4 (End of Week 4): Operational Alert Delivery
Status: In Progress
Delivered:
- SQLite persistence (cycles/events/raw items)
- `run-cycle` operational command
- `start-scheduler` interval command (`--max-runs` support)
In progress:
- output contract stabilization for Moltis chat alert payloads

### Milestone 5 (End of Week 5): QA and Hardening
Status: Not Started
Planned:
- Replay tests with saved fixtures
- Failure-path coverage expansion
- Threshold tuning and parser hardening

### Milestone 6 (End of Week 6): MVP Pilot and Sign-off
Status: Not Started
Planned:
- 7-cycle monitored pilot
- KPI validation and final acceptance review

## KPI Tracking (Weekly)
- Duplicate alert rate (target <= 10%).
- Traceable alerts with source/timestamp (target 100%).
- High/critical corroboration rate (target >= 90% where available).
- Consecutive successful cycles without blocking error (target >= 7 for sign-off).

## Immediate Next Actions
1. Add event-level corroboration metadata persistence.
2. Implement stronger parser rules for selected high-priority feeds.
3. Add replay/integration fixtures and scenario tests.
4. Finalize Moltis alert output contract and validate format in scheduled runs.
5. Execute pilot run and record KPI report.

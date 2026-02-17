# Development Roadmap - Dynamic Disaster Intelligence Assistant

Date: 2026-02-17
Version: 0.5

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
Pending for final sign-off:
- reliefweb activation and re-pilot with richer event coverage
- NGO source stabilization
- hardening-gate status `pass` on non-zero event dataset

## Immediate Next Actions
1. Enable ReliefWeb and rerun 7-cycle pilot.
2. Replace failing NGO feed and validate source-health failure thresholds.
3. Capture final KPI evidence and publish MVP sign-off.

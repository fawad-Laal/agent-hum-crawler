# Product Spec - Dynamic Disaster Intelligence Assistant

Date: 2026-02-17
Version: 0.1 (MVP)

## 1. Problem Statement
Users need rapid, reliable updates about disasters (cyclones, floods, earthquakes, conflict emergencies, etc.) in selected countries without manually checking many sites.

## 2. Product Goal
Create a Moltis-based assistant that:
- accepts user-defined monitoring inputs (countries, disaster types, interval)
- monitors online sources continuously
- sends concise, actionable alerts in Moltis chat
- reduces noise through verification and deduplication

## 3. Target Users
- Individual operators tracking emergency situations
- Humanitarian/planning users needing quick situational awareness

## 4. In Scope (MVP)
- Dynamic user configuration at runtime:
  - countries (required)
  - disaster types (required)
  - interval minutes (required)
  - optional subregions and source preferences
- Monitoring cycle with source prioritization and filtering
- Severity classification: `low`, `medium`, `high`, `critical`
- Confidence classification: `low`, `medium`, `high`
- Moltis chat alerts only
- Event deduplication and change detection

## 5. Out of Scope (MVP)
- Automated social posting
- Automated field-response actions
- Telegram notifications (phase 2)

## 6. Functional Requirements
1. The system must ask for required monitoring inputs before first run.
2. The system must validate input values and ask clarifying questions when needed.
3. The system must fetch updates from trusted source categories.
4. The system must generate event records with source URLs and timestamps.
5. The system must assign severity and confidence per event.
6. The system must suppress duplicate/near-duplicate alerts.
7. The system must alert on all `high` and `critical` events.
8. The system must alert on `medium` events only when changed meaningfully.
9. The system must show next planned check time.

## 7. Non-Functional Requirements
- Reliability: no fabricated source links.
- Latency: one cycle should finish within configured interval budget.
- Safety: present uncertainty clearly; avoid single-source certainty.
- Traceability: every alert includes source URL(s) and update time.

## 8. Success Metrics (MVP)
- >= 90% of high/critical alerts contain at least two corroborating reliable sources (where available).
- <= 10% duplicate alerts across 24-hour window.
- 100% alerts include timestamp, severity, confidence, and source URLs.
- User can reconfigure countries/types/interval in a single interaction.

## 9. Risks
- Source volatility and inconsistent publishing formats.
- False positives from unverified social content.
- Alert fatigue if dedupe/change logic is weak.

## 10. MVP Exit Criteria
- End-to-end monitoring with dynamic config works for at least two countries and three disaster types.
- Alert formatting remains stable for at least 7 consecutive cycles.
- Manual review confirms source integrity and low duplicate rate.

# Test Plan - Dynamic Disaster Monitoring Agent

Date: 2026-02-17

## 1. Test Scope
- Input collection and validation
- Monitoring and normalization pipeline
- Severity/confidence assignment
- Deduplication/change detection
- Moltis alert output integrity

## 2. Test Types
- Unit: validation, hashing, severity rules, formatter
- Integration: full cycle with mocked source inputs
- Scenario: multi-country mixed-disaster updates across several cycles
- Failure: provider/source/network partial failures

## 3. Key Test Cases
1. Missing required config input -> clarifying prompt appears.
2. Invalid interval (<5 or >1440) -> rejected with correction hint.
3. Single-source unverified event -> low confidence, not high certainty wording.
4. Repeat event unchanged next cycle -> no duplicate alert.
5. Medium event escalates -> alert emitted as changed update.
6. Critical event during quiet hours -> still emitted.
7. Alert payload missing URL/timestamp -> test fails.

## 4. Acceptance Gates
- Gate A: all required fields validated.
- Gate B: event schema completeness 100%.
- Gate C: duplicate suppression target met.
- Gate D: every emitted alert has source traceability.

## 5. Manual Review Checklist
- Severity and confidence are reasonable for sampled events.
- Facts vs inference language is clear.
- Final output is concise and operational.

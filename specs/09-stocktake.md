# Stocktake - Current State

Date: 2026-02-20

## Snapshot
- Roadmap position: Post-MVP, Milestones 1-6 completed.
- Core engine status: operational (`run-cycle`, `start-scheduler`, `write-report`, `write-situation-analysis`).
- QA status: replay fixtures + quality metrics + source health analytics + report quality gates available.
- Ontology/SA status: graph ontology and OCHA-style Situation Analysis engine operational.
- Test status: 114 passing tests.

## What Is Stable
- Runtime config intake and validation.
- Multi-source collection orchestration.
- Dedupe/change detection with corroboration-aware confidence/severity.
- Persistence for cycles, events, raw items, and connector/feed health.
- Alert output contract for downstream Moltis message formatting.
- GraphRAG long-form reporting with quality gates.
- Template-driven report rendering (brief, detailed, default, situation analysis).
- Humanitarian ontology graph with multi-pattern NLP extraction.
- OCHA-style Situation Analysis rendering (15 sections, deterministic + optional LLM).
- Country gazetteers (Madagascar 22 provinces, Mozambique 10 provinces).
- Auto-inference of event name/type and disaster classification from evidence.
- Dashboard API with run-cycle, write-report, write-situation-analysis, source-check, workbench.
- React operator dashboard with monitoring, report workbench, and SA generation.
- Feature flag system with centralized config.
- Source freshness diagnostics and stale-policy enforcement.
- Security/auth baseline validation script.
- E2E deterministic regression gate with artifact capture.

## What Still Needs Hardening
- Province-level figure distribution (national totals → admin1 breakdown by geo-mention).
- Full-article content fetching to improve NLP extraction yield from short RSS snippets.
- Forecast/risk data extraction from evidence text.
- Ontology figure persistence in DB for cross-report trending.
- Country gazetteer expansion beyond Madagascar/Mozambique.
- Access constraint extraction quality (currently keyword-based, could benefit from NLP).
- Streaming/tool-registry conformance rollout.
- Runtime auth-path probes for behavioral security validation.

## Definition of Readiness for Next Phase
- SA report produces populated admin1 impact tables (not just national aggregates).
- Evidence text quality improved via full-article fetching for at least top-3 connectors.
- Forecast section populated from actual weather/risk evidence.
- All 114+ tests continue to pass after each improvement.

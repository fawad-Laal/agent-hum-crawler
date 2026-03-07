# Moltis Roadmap Index

Date: 2026-03-07

## Active Phases

| Phase | Document | Status |
|-------|----------|--------|
| **Project Clarity** (SA Reduced++) | [project-clarity-roadmap.md](project-clarity-roadmap.md) | **Active** — Phases 1-4 complete; Phase 5 Phoenix remediation and Phase 6 backend hardening tracked |
| **Project Phoenix** (Frontend Rewrite) | [frontend-rewrite-roadmap.md](frontend-rewrite-roadmap.md) | **Active** — Phases 1-9 complete in codebase; Phase 10 testing/release and review-driven remediation remain |

## Completed / Archived Phases

| Phase | Document | Status |
|-------|----------|--------|
| MVP Pipeline (Milestones 1–6) | [archive/mvp-roadmap.md](archive/mvp-roadmap.md) | **Closed** — All 6 milestones delivered |
| Frontend Dashboard (Phases 0–3.5) | [archive/frontend-roadmap.md](archive/frontend-roadmap.md) | **Closed** — Baseline through SA UI delivered |

## Review-Driven Priorities

The March 7, 2026 whole-app re-review added roadmap-critical follow-up work that is now tracked in the active roadmap documents:

- Phoenix remediation for API/UI contract drift, real job/SSE integration, feature-flag data-shape safety, and roadmap/code status reconciliation.
- Backend remediation for storage path decoupling from `~/.moltis`, DB schema/runtime drift checks, and job-store TTL correctness.
- Explicit QA gates, measurable acceptance criteria, and regression evidence before any roadmap item can be closed.

## Reference

| Document | Location |
|----------|----------|
| Deep Analysis (March 2026) | [../analysis/moltis_deep_analysis_march2026.md](../analysis/moltis_deep_analysis_march2026.md) |
| Whole App Review (March 2026) | [../analysis/whole-app-review-march2026.md](../analysis/whole-app-review-march2026.md) |
| Frontend Audit Report | [../analysis/frontend-audit-report.md](../analysis/frontend-audit-report.md) |
| SA Quality Root Cause Analysis | [../analysis/sa-improvement-analysis.md](../analysis/sa-improvement-analysis.md) |
| LLM Intelligence Layer v1 Spec | [../../specs/15-llm-intelligence-layer-v1.md](../../specs/15-llm-intelligence-layer-v1.md) |
| System Architecture | [../../specs/06-architecture.md](../../specs/06-architecture.md) |

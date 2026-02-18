# Moltis Operations Alignment

Date: 2026-02-18
Status: Active

## Purpose
Define how this project should use Moltis features correctly in production-like operation.

## 1. System Prompt Usage
- Use Moltis dynamic prompt assembly as-is (base intro, identity, soul, user profile, project context, runtime context, skills, workspace files, tools, guidelines).
- Keep project behavior rules in repository `AGENTS.md`.
- Keep persona files in `~/.moltis/`:
  - `IDENTITY.md`
  - `SOUL.md`
  - `USER.md`
  - optional `TOOLS.md`

## 2. Prompt Governance Rules for This Agent
- Prefer trusted source retrieval over free-form generation.
- Require source URL + published time in all event outputs.
- Use uncertainty language when corroboration is weak.
- Keep instructions compact to control token cost with many tools.

## 3. Source Collection Policy
- Default policy:
  1. API connectors first (ReliefWeb, other formal APIs).
  2. RSS/Atom feed connectors second.
  3. Browser automation only when API/feed path is unavailable or incomplete.
- Browser mode should be restricted to trusted domains and sandboxed where possible.

## 4. Streaming Behavior Expectations
- Streaming must stay enabled for long multi-source cycles.
- User should receive:
  - thinking state
  - tool call state transitions
  - text deltas
  - final result
- Tool execution should remain parallel for independent connectors.

## 5. Metrics and Tracing Alignment
- Enable Moltis metrics and Prometheus export in deployment profile.
- Minimum endpoint checks:
  - `/metrics`
  - `/api/metrics`
  - `/api/metrics/summary`
  - `/api/metrics/history`
- Correlate gateway metrics with app-level reports:
  - `quality-report`
  - `source-health`
  - `hardening-gate`

## 6. Readiness Checklist
- Prompt layering verified in live session.
- Streaming + tool-call events verified in live session.
- API-first / browser-fallback policy observed in cycle logs.
- Metrics endpoints reachable and returning data.
- Pilot run evidence captured with `pilot-run`.

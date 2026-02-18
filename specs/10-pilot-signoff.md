# Pilot Sign-off - Milestone 6

Date: 2026-02-18

## Pilot Scope
- Executed 7 consecutive cycles via `pilot-run`.
- Runtime filters: countries=`Madagascar`, disaster_types=`cyclone/storm`, limit=`10`, cycles=`7`.
- ReliefWeb enabled and returning matched items.

## KPI Snapshot
From `pilot-run` / `quality-report --limit 7`:
- cycles_analyzed: 7
- events_analyzed: 21
- duplicate_rate_estimate: 1.0
- traceable_rate: 1.0

From `pilot-run` / `source-health --limit 7`:
- Connector failure rates:
  - `reliefweb`: 0.0
  - `ngo_feeds`: 0.0
  - `government_feeds`: 0.0
  - `un_humanitarian_feeds`: 0.0

From `hardening-gate --limit 7`:
- status: `fail`
- reason: duplicate rate threshold failed
- duplicate_rate_ok: `false` (duplicate_rate = 1.0, threshold = 0.10)
- traceable_rate_ok: `true`
- connector_failure_ok: `true`

## Outcome
- Engineering pipeline stability: **PASS**
  - 7-cycle execution completed without blocking runtime errors.
  - Scheduler and cycle persistence remained stable.
  - Health and quality analytics reported correctly.

- Data-quality sign-off: **FAIL**
  - Events were collected and matched, but dedupe/change thresholds were not met.
  - Hardening gate failed due duplicate-rate breach.

## Required Actions Before Final Production Sign-off
1. Enable approved ReliefWeb appname and rerun pilot with live humanitarian coverage.
2. Replace or disable failing NGO feed (`IFRC`) and onboard alternative NGO source.
3. Reduce duplicate-rate inflation in dedupe/change logic and re-run 7-cycle pilot.
4. Re-run `quality-report`, `source-health`, and `hardening-gate` and confirm gate status `pass`.
5. Capture verified Moltis conformance evidence (`streaming`, `tool registry`, `MCP disable fallback`, `auth/proxy matrix`) and flip failed checks to pass only after direct validation.

## Moltis Conformance Evidence (Required)
- Tool registry source metadata evidence:
  - sample schemas show `source` and `mcpServer` fields.
- Streaming lifecycle evidence:
  - event sequence captured for one long run (`thinking`, `delta`, `tool_call_start`, `tool_call_end`, `thinking_done`).
- MCP-disabled fallback evidence:
  - session with MCP disabled still executes builtin-only workflow.
- Auth/proxy matrix evidence:
  - local/no-credential, remote/setup-required, and proxy-forced-remote checks documented.
- Consolidated conformance status:
  - `python -m agent_hum_crawler.main conformance-report ...` output attached.

## LLM Evidence (Step 2 Upgrade)
- `pilot-run` now emits per-cycle LLM metrics:
  - `attempted_count`
  - `enriched_count`
  - `fallback_count`
  - `provider_error_count`
  - `validation_fail_count`
  - `insufficient_text_count`
- `quality-report` now emits aggregated LLM metrics:
  - `llm_enriched_events`
  - `llm_enrichment_rate`
  - `citation_coverage_rate`
  - `llm_provider_error_count`
  - `llm_validation_fail_count`
- Citation locking now requires exact quote spans (`quote_start`, `quote_end`) that match source text slices.

### Controlled LLM Window (2026-02-18)
Run config:
- `LLM_ENRICHMENT_ENABLED=true` (temporary shell override for run window)
- countries=`Madagascar`
- disaster_types=`cyclone/storm`
- cycles=`3`
- limit=`5`
- `--enforce-llm-quality`
- thresholds: `min_llm_enrichment_rate=0.10`, `min_citation_coverage_rate=0.95`

Measured outputs:
- `llm_attempted_events`: 3
- `llm_enriched_events`: 0
- `llm_fallback_events`: 3
- `llm_provider_error_count`: 0
- `llm_validation_fail_count`: 3
- `llm_enrichment_rate`: 0.0
- `citation_coverage_rate`: 0.0

LLM gate result (`llm-report --enforce-llm-quality`):
- status: `fail`
- `llm_enrichment_rate_ok`: `false`
- `citation_coverage_ok`: `false`

Hardening impact:
- `hardening-gate` now includes LLM checks.
- Current status remains `fail` with both classic dedupe and LLM quality checks failing.

### Controlled LLM Window After Span-Normalization Update (2026-02-18)
Adjustment:
- Citation span validation now resolves index mismatches by deriving spans from quote text with minor normalization, then stores exact source slices.

Run config:
- `LLM_ENRICHMENT_ENABLED=true` (temporary shell override for run window)
- countries=`Madagascar`
- disaster_types=`cyclone/storm`
- cycles=`3`
- limit=`5`
- `--enforce-llm-quality`
- thresholds: `min_llm_enrichment_rate=0.10`, `min_citation_coverage_rate=0.95`

Measured outputs:
- `llm_attempted_events`: 3
- `llm_enriched_events`: 3
- `llm_fallback_events`: 0
- `llm_provider_error_count`: 0
- `llm_validation_fail_count`: 0
- `llm_enrichment_rate`: 1.0
- `citation_coverage_rate`: 1.0

LLM gate result (`llm-report --enforce-llm-quality`):
- status: `pass`
- `llm_enrichment_rate_ok`: `true`
- `citation_coverage_ok`: `true`

Hardening impact:
- LLM checks are now passing.
- Overall `hardening-gate` still `fail` due duplicate-rate check (`duplicate_rate_ok=false`).

### 7-Cycle Enforced Pilot With Reset State (2026-02-18)
Run config:
- `LLM_ENRICHMENT_ENABLED=true` (temporary shell override for run window)
- countries=`Madagascar,Mozambique`
- disaster_types=`cyclone/storm,flood`
- cycles=`7`
- limit=`10`
- `--enforce-llm-quality`
- `--reset-state-before-run`

Measured outputs:
- `events_analyzed`: 2
- `duplicate_rate_estimate`: 0.0
- `traceable_rate`: 1.0
- `llm_attempted_events`: 2
- `llm_enriched_events`: 2
- `llm_fallback_events`: 0
- `llm_validation_fail_count`: 0
- `llm_enrichment_rate`: 1.0
- `citation_coverage_rate`: 1.0

Gate outcomes:
- `hardening-gate`: `pass`
- `llm-report --enforce-llm-quality`: `pass`
- `conformance-report`: `warning` (only because conformance checks are still `pending`, not because hardening failed)

### Current Conformance Run (2026-02-18)
- `moltis_conformance.status`: `fail`
- Checks:
  - `streaming_event_lifecycle`: `fail`
  - `tool_registry_source_metadata`: `fail`
  - `mcp_disable_builtin_fallback`: `fail`
  - `auth_matrix_local_remote_proxy`: `fail`
  - `proxy_hardening_configuration`: `fail`
- Note: strict pass/fail mode used, with any unverified check marked `fail` (no pending values retained).

## Commands Used
```powershell
python -m agent_hum_crawler.main run-cycle --countries "Pakistan" --disaster-types "flood,earthquake" --interval 30 --limit 1
python -m agent_hum_crawler.main quality-report --limit 7
python -m agent_hum_crawler.main source-health --limit 7
python -m agent_hum_crawler.main hardening-gate --limit 7
python -m agent_hum_crawler.main pilot-run --countries "Madagascar" --disaster-types "cyclone/storm" --limit 10 --cycles 7 --sleep-seconds 0 --include-content
python -m agent_hum_crawler.main conformance-report --limit 7 --streaming-event-lifecycle fail --tool-registry-source-metadata fail --mcp-disable-builtin-fallback fail --auth-matrix-local-remote-proxy fail --proxy-hardening-configuration fail
```

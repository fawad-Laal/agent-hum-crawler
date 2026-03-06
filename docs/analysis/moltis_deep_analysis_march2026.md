# Moltis Deep Analysis - March 2026 (Revalidated)

Date: 2026-03-04
Scope: backend (`src/agent_hum_crawler`), API routes (`src/agent_hum_crawler/api`), Phoenix UI (`ui-phoenix`), and project docs.

## Executive Summary

This pass corrects several outdated assumptions in the previous analysis and focuses on issues that are currently true in code.

Most important corrections:
- `build_graph_context()` already reads `RawItemRecord` and joins full raw text into evidence (`reporting.py`).
- Situation Analysis narrative generation is already two-pass (`_generate_llm_narratives()` in `situation_analysis.py`).
- Rust `detect_admin_area` is already exposed in `rust_accel.py`.

Highest-impact remaining gaps:
1. Enrichment path mismatch: cycle runtime uses per-item LLM enrichment, while batch enrichment exists but is unused.
2. Evidence query path scales poorly: broad table reads then Python-side filtering/parsing.
3. Orchestration is fragmented across CLI, API routes, and workbench with duplicated report/SA flow.
4. Operational docs drift from actual behavior (DB path, architecture claims), which increases onboarding and debugging time.
5. ReliefWeb ingestion underuses structured API fields (`headline.summary`, file metadata) and lacks operator-grade extraction telemetry.

## 1) Pipeline Quality and LLM Use

### What is good now
- SA generation supports deterministic and LLM paths.
- SA LLM generation is two-pass (core + sectoral), with citation index injection.
- Citation cleanup/validation exists before final render.

### Current issues

1. Runtime still uses per-item enrichment in cycle flow.
- `run_cycle_once()` calls `enrich_events_with_llm()` (single-item calls), not `enrich_events_batch()`.
- Result: higher latency and cost variance at scale.

2. Event summaries are hard-capped to 320 chars.
- Both enrichment paths truncate summary to `summary[:320]`.
- This cap compresses narrative signal before report ranking/scoring.

3. Batch text cap (`_BATCH_TEXT_CAP = 400`) exists but is not the dominant bottleneck today.
- Because batch mode is not currently wired into cycle flow, tuning this constant alone has limited effect.

### Recommendations

R1. Switch cycle enrichment to batch mode with fallback.
- In `cycle.py`, call `enrich_events_batch()` by default when LLM is enabled.
- Fallback to single-item only on schema/provider failure.
- Add metrics: `llm_mode=batch|single`, median latency per enriched event.

R2. Separate storage summary vs analysis excerpt.
- Keep `summary` short for UI (for example 320 chars).
- Add `analysis_excerpt` (1000-2000 chars) to `EventRecord` for report/SA building.

R3. Add enrichment policy by connector/source confidence.
- Use shorter excerpts for low-trust sources.
- Use larger excerpts for ReliefWeb/UN/government sources.

Acceptance criteria:
- Same cycle inputs produce >=20% lower LLM call count in logs.
- `build_graph_context()` can consume `analysis_excerpt` when present.
- Quality gate `citation_density` and `key_figure_coverage` do not regress.

## 2) Data Access and Performance

### Current issues

1. Query pattern is wide then filtered in Python.
- `build_graph_context()` loads events/raw items for selected cycles, then applies country/disaster/date filters in Python.
- This is simple but expensive when cycle history grows.

2. JSON payload parsing is repeated at query time.
- `RawItemRecord.payload_json` is parsed row-by-row to extract `text`.
- This increases CPU and response latency for report/SA endpoints.

3. Data model lacks query-oriented extracted fields.
- Raw JSON blob is convenient for ingestion, not for high-frequency graph/report retrieval.

### Recommendations

R4. Push core filters to SQL.
- Apply country/disaster/date filters in the DB query where possible.
- Keep balancing and scoring logic in Python.

R5. Add extracted columns to `RawItemRecord`.
- `text_excerpt` (TEXT)
- `text_char_count` (INTEGER)
- `extraction_method` (TEXT: trafilatura|bs4|pdf|mixed)
- `has_attachments` (INTEGER)

R6. Add indexes for frequent lookups.
- `eventrecord(cycle_id, country, disaster_type)`
- `eventrecord(cycle_id, url)`
- `rawitemrecord(cycle_id, url)`

Acceptance criteria:
- `write-report` and `write-situation-analysis` median response time improved on a DB with >=50 cycles.
- Profile shows lower Python JSON parse time in `build_graph_context()`.

## 3) Extraction Quality (RSS/HTML/PDF/ReliefWeb)

### What is good now
- Feed connector already does content-level extraction and appends PDF text.
- ReliefWeb connector pulls `body-html`, metadata, and attachments with pagination.

### Current issues

1. Fallback HTML extraction can be noisy.
- When trafilatura fails, bs4 `get_text()` can include navigation boilerplate.

2. Attachment extraction quality is not persisted as first-class metadata.
- You cannot easily audit which events are thin because extraction failed vs source was short.

3. Multi-format documents are still under-leveraged.
- ReliefWeb often ships useful `.docx/.xlsx` content not treated with structured extraction strategy.

### Recommendations

R7. Add extraction confidence scoring.
- Derive score from char count, boilerplate ratio, and source type.
- Persist score for downstream ranking.

R8. Add secondary converter path for weak extraction cases.
- Use converter fallback when primary extraction is short/noisy.
- Keep feature-flagged until quality benchmark passes.

R9. Add extraction diagnostics endpoint.
- Expose top failing sources/connectors by low extraction confidence.

Acceptance criteria:
- Dashboard can show low-confidence extraction items.
- At least one measurable increase in average useful chars for ReliefWeb-heavy runs.

## 4) Ontology and Report Semantics

### What is good now
- Ontology supports impacts/needs/risks/responses/claims and sector summary.
- Rust acceleration hooks are already integrated with Python fallback.

### Current issues

1. Most ontology queries remain list scans.
- Works now, but scales poorly with larger evidence sets.

2. Geo matching is still brittle for naming variants.
- Canonicalization and fuzzy matching can be improved for admin-level consistency.

3. No explicit provenance score at node level.
- Claims are tracked, but ranking in narrative generation could better use confidence/credibility/source freshness.

### Recommendations

R10. Build optional in-memory indexes after ontology build.
- `geo -> impacts`
- `need_type -> needs`
- `horizon -> risks`

R11. Add geo canonicalization pipeline.
- Exact gazetteer match first.
- Fuzzy fallback with confidence threshold.
- Store raw and canonical names side-by-side for audit.

R12. Add per-node evidence strength score.
- Weighted blend of source credibility, corroboration count, and recency.
- Use score when selecting bullets/table rows and LLM digest entries.

Acceptance criteria:
- Deterministic report output is stable for synonymous geo inputs.
- Ontology query time drops on large evidence sets.

## 5) API and Job Orchestration

### Current issues

1. Orchestration is split across multiple places.
- CLI, cycle route, report route, SA route, and workbench each implement variants of the same flow.

2. Concurrency policy is inconsistent.
- Cycle/pipeline routes use exclusive lock.
- SA/report/workbench jobs are non-exclusive, allowing high concurrent LLM workload spikes.

3. In-process job store has no bounded retention strategy.
- Potential memory growth in long-lived server sessions.

### Recommendations

R13. Route all long workflows through `PipelineCoordinator` variants.
- Keep routes thin and declarative.
- Consolidate progress/error schema.

R14. Add queue policy and rate limits by job type.
- `exclusive` for pipeline + optional cap for SA/report LLM jobs.
- Return actionable 429/409 error payloads.

R15. Add job retention policy.
- Purge completed/error jobs older than TTL in in-memory backend.

Acceptance criteria:
- One shared workflow contract for CLI and API job results.
- Load test shows stable memory and predictable queue behavior.

## 6) Frontend and DX Observability

### Current issues

1. Polling is fixed-interval with no adaptive backoff.
- May over-poll during long-running jobs.

2. Security status semantics can be clearer.
- `security-baseline-card.tsx` treats some fail combinations as `warn`.
- This can understate risk for operators.

3. Dev logs are verbose in API client and can be noisy.

### Recommendations

R16. Add polling backoff and cancellation.
- Progressive intervals and explicit abort on route change/unmount.

R17. Refine security state mapping.
- Promote combined hardening fail + E2E fail to explicit critical state.
- Add tooltip text explaining why status is pass/warn/fail.

R18. Add operator-facing API timings.
- Show end-to-end durations and stage timings in UI job panel.

Acceptance criteria:
- Lower network request volume during long jobs.
- Clearer operator interpretation of security baseline state.

## 7) Documentation Content Accuracy

### Current issues

1. The previous deep analysis document contains outdated findings.
- It states some fixes are missing when they already exist.

2. README architecture details drift from implementation.
- Example: DB naming/path descriptions do not match actual defaults.

3. Multiple files show mojibake in displayed symbols/hyphens.
- This hurts trust and readability for contributors.

### Recommendations

R19. Add documentation verification checklist to PR flow.
- For each architectural claim, link one source file/function.

R20. Standardize encoding and lint docs.
- Enforce UTF-8 and add a simple check for common mojibake sequences.

R21. Keep one source of truth for runtime defaults.
- Generate docs snippets from code constants where practical.

Acceptance criteria:
- README matches runtime defaults from `database.py` and `settings.py`.
- No encoding artifacts in core docs after lint pass.

## 8) ReliefWeb API Revalidation and Integration

This section is based on the official ReliefWeb API docs at `https://apidoc.reliefweb.int/`.
MarkItDown reference for document conversion: `https://github.com/microsoft/markitdown`.

### Confirmed from official docs

1. Current API version is `v2`; `v1` is deprecated.
2. `appname` is required and must be pre-approved (policy noted from Nov 2025 onward).
3. Reports support both narrative fields and attachments:
- Narrative fields: `body`, `body-html`, `headline.title`, `headline.summary`.
- Attachment fields: `file.url`, `file.mimetype`, `file.filename`, `file.description`, `file.preview.*`.
4. API result includes pagination links (`links.next`) and response timing (`time`), useful for monitoring.

### Independent validation run (2026-03-04)

Using the project's configured approved `RELIEFWEB_APPNAME`, a live probe against
`/v2/reports` was executed with explicit `fields.include` and `limit=100`.

Observed sample results:
- `sample_size=100`
- `body/body-html` present in `81/100`
- attachments (`file`) present in `72/100`
- attachment MIME metadata present in `72/72` attachment-bearing items
- `headline` object present in `0/100` (so `headline.summary` also `0/100`)

Interpretation:
- Attachment extraction and monitoring are high-priority and broadly applicable.
- `headline.summary` should be treated as optional/sparse, not a primary dependency.

### Gap versus current connector

In `connectors/reliefweb.py`, current query includes:
- `body`, `body-html`, `file`, and key metadata fields.

But current mapping behavior still misses important signal:
- `headline.summary` is not requested or ingested.
- Attachment handling is extension-based (`.pdf`) instead of MIME-first.
- Non-PDF attachments are only tracked as `document_html` sources, not parsed.
- No extraction ledger exists to show per-attachment parse success/failure.

### Required integration changes

R22. Expand requested fields for reports.
- Add to `fields.include`:
`headline.title`, `headline.summary`, `file.mimetype`, `file.filename`, `file.description`, `origin`.
- Keep `body-html` and `body`; use a deterministic merge policy.
- Note: `headline.*` appears sparse in live samples; include for compatibility but do not rely on it.

R23. Build narrative text with a strict precedence policy.
- Candidate order:
1. `headline.summary` (short editorial abstract)
2. cleaned `body-html`/`body`
3. fetched page fallback (`_fetch_page_text`)
- Persist source of each text segment (for explainability in UI).

R24. Parse attachments by MIME type, not extension.
- Use `file.mimetype` first:
`application/pdf`, `application/msword`,
`application/vnd.openxmlformats-officedocument.wordprocessingml.document`,
`application/vnd.ms-excel`,
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- Keep extension fallback only when MIME is missing.
- For PDFs and Office files, require local file download first, then conversion.

R25. Add attachment extraction pipeline contract.
- Introduce extractor dispatch:
`extract_document(file_url, mimetype) -> ExtractionResult`.
- `ExtractionResult` should include:
`text`, `char_count`, `method`, `status`, `error`, `duration_ms`.
- Implement MarkItDown-first path for document conversion:
  - Install: `pip install 'markitdown[pdf,docx,xlsx]'`
  - Use Python API: `MarkItDown().convert(local_path)` and persist `text_content`
  - Fallback chain when output is empty/low-yield:
    1. existing PDF extractors (`pdfplumber`/`pypdf`)
    2. optional Azure Document Intelligence mode for difficult files
  - Persist `method` values such as `markitdown`, `pdfplumber`, `pypdf`, `azure_docint`.

### Monitoring and user visibility requirements

R26. Add extraction observability records.
- Add DB table `ExtractionRecord` (or JSON column on raw items) with:
`cycle_id`, `event_url`, `file_url`, `mimetype`, `filename`, `status`,
`method`, `char_count`, `duration_ms`, `error`.

R27. Add API endpoint for extraction diagnostics.
- Example:
`GET /api/sources/extraction-diagnostics?connector=reliefweb&limit=200`
- Return:
success rate, skip reasons, avg chars per file type, top failing MIME types,
top failing domains, and latest failures.

R28. Add CLI diagnostics command.
- Example:
`agent-hum-crawler extraction-report --connector reliefweb --limit-cycles 20`
- Include:
parsed vs skipped counts, parse quality buckets, and attachment format mix.

R29. Expose monitoring in Phoenix UI.
- Add a panel in Sources/System with:
`attachments_seen`, `attachments_parsed`, `parse_success_rate`,
`avg_chars_extracted`, `top_errors`, and trend chart by cycle.

### Acceptance criteria for ReliefWeb integration

1. For a fixed ReliefWeb sample set, attachment parse coverage increases materially (PDF + Office docs).
2. Every skipped/failed attachment has a stored reason and is visible via API/UI.
3. Operators can identify low-yield sources and parser regressions within one dashboard view.
4. `headline.summary` appears in stored payload and is used in report/SA evidence assembly when available.
5. Full-PDF extraction target: at least 90% of ReliefWeb PDF attachments produce non-empty extracted text (`char_count >= 500`) via MarkItDown or fallback.
6. For each parsed PDF, store extraction lineage (`downloaded=true`, `method`, `duration_ms`, `char_count`) for auditability.

## Prioritized Plan

### P0 (next 3-5 days)
- R1, R4, R6, R13, R19, R22, R24, R26

### P1 (next 1-2 weeks)
- R2, R5, R10, R14, R16, R17, R23, R27, R28

### P2 (next 2-4 weeks)
- R3, R8, R9, R11, R12, R15, R18, R20, R21, R25, R29

## Suggested Tracking Table

| ID | Owner | Target | Status | KPI |
|---|---|---|---|---|
| R1 | Backend | 1 week | planned | LLM calls per cycle |
| R4 | Backend | 1 week | planned | report build latency |
| R6 | Backend | 1 week | planned | query CPU time |
| R13 | Platform | 1 week | planned | duplicated flow count |
| R16 | Frontend | 1 week | planned | polling request volume |
| R19 | Docs | 1 week | planned | doc/code drift issues |

## Final Note

This update is intentionally implementation-grounded. Any future analysis should be generated from current code inspection first, then recommendations second, to avoid repeating stale conclusions.

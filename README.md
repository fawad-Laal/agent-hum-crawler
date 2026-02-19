# Agent HUM Crawler

Dynamic disaster-intelligence monitoring assistant.

## Current Highlights
- Dynamic multi-source monitoring with country/disaster filters.
- SQLite persistence for cycle, event, and source-health evidence.
- GraphRAG-style long-form reporting from persisted evidence (no vector DB required).
- Template-driven report formatting (`default`, `brief`, `detailed`).
- AI-assisted report drafting with deterministic fallback when LLM is unavailable.
- Deterministic quality gates for reports, LLM enrichment, hardening, and conformance.

## Stack
- Python 3.11+
- `pydantic` for schema validation
- `httpx` for API/web requests
- `trafilatura` + `beautifulsoup4` for text extraction
- `feedparser` for RSS/Atom connectors
- `pypdf` + `pdfplumber` for document extraction (next expansion)
- `APScheduler` for scheduling (next milestone)
- `sqlmodel` + SQLite for cycle persistence
- `pytest` for tests

## Environment
Create `.env` with:

```env
RELIEFWEB_ENABLED=true
RELIEFWEB_APPNAME=your_approved_reliefweb_appname
LLM_ENRICHMENT_ENABLED=false
OPENAI_API_KEY=... # required only when LLM_ENRICHMENT_ENABLED=true
OPENAI_MODEL=gpt-4.1-mini
```

ReliefWeb appname request: https://apidoc.reliefweb.int/parameters#appname
If approval is pending, set `RELIEFWEB_ENABLED=false` to run fallback connectors only.
When `LLM_ENRICHMENT_ENABLED=true`, the pipeline attempts LLM summary/severity/confidence enrichment with citation locking (`url + quote + quote_start + quote_end`). On any LLM failure, it falls back to deterministic rules.
Citation locking is strict: `quote` must exactly equal `source_text[quote_start:quote_end]`.

Report drafting uses `OPENAI_API_KEY` when `write-report --use-llm` is requested. If the key/model call fails, report generation falls back to deterministic rendering.

## Country Source Allowlists
- Active file: `config/country_sources.json`
- Template: `config/country_sources.example.json`

Per-country feeds from this file are merged into connector selection for `run-cycle` and `start-scheduler`.

Current global local-news set includes:
- BBC World
- Al Jazeera English
- AllAfrica Latest
- Africanews
- Africa News Agency (ANA)
- The Guardian World
- Reuters World (Google News Reuters query feed)

Government connectors include:
- USGS Earthquakes
- GDACS

## Install

```powershell
python -m pip install -e .[dev]
```

## Commands

Interactive intake:

```powershell
python -m agent_hum_crawler.main intake
```

Fetch ReliefWeb only:

```powershell
python -m agent_hum_crawler.main fetch-reliefweb --countries "Pakistan,Bangladesh" --disaster-types "flood,cyclone/storm" --interval 30 --limit 20 --include-content
```

Run one full monitoring cycle (ReliefWeb + government + UN + NGO + local-news feeds):

```powershell
python -m agent_hum_crawler.main run-cycle --countries "Pakistan,Bangladesh" --disaster-types "flood,cyclone/storm,earthquake" --interval 30 --limit 10 --include-content --local-news-feeds "https://example.com/rss.xml"
```

`run-cycle` returns an alert contract with these sections:
- `critical_high_alerts`
- `medium_updates`
- `watchlist_signals`
- `source_log`
- `next_check_time`

Use saved config for cycle:

```powershell
python -m agent_hum_crawler.main run-cycle --use-saved-config --limit 10
```

Show persisted cycles:

```powershell
python -m agent_hum_crawler.main show-cycles --limit 10
```

Show quality metrics from recent cycles:

```powershell
python -m agent_hum_crawler.main quality-report --limit 10
```

`quality-report` includes LLM metrics:
- `llm_attempted_events`
- `llm_enriched_events`
- `llm_fallback_events`
- `llm_enrichment_rate`
- `citation_coverage_rate`
- `llm_provider_error_count`
- `llm_validation_fail_count`

Show LLM quality gate summary:

```powershell
python -m agent_hum_crawler.main llm-report --limit 10 --min-llm-enrichment-rate 0.10 --min-citation-coverage-rate 0.95
```

Show connector/feed health analytics:

```powershell
python -m agent_hum_crawler.main source-health --limit 10
```

Evaluate hardening gate thresholds:

```powershell
python -m agent_hum_crawler.main hardening-gate --limit 10 --min-llm-enrichment-rate 0.10 --min-citation-coverage-rate 0.95
```

Run an automated pilot evidence pack (N cycles + quality + health + gate):

```powershell
python -m agent_hum_crawler.main pilot-run --countries "Madagascar" --disaster-types "cyclone/storm" --limit 10 --cycles 7 --sleep-seconds 0 --include-content
```

For reproducible pilot windows in rapid back-to-back runs, reset state before pilot:

```powershell
python -m agent_hum_crawler.main pilot-run --countries "Madagascar,Mozambique" --disaster-types "cyclone/storm,flood" --limit 10 --cycles 7 --sleep-seconds 0 --include-content --enforce-llm-quality --reset-state-before-run
```

Run consolidated conformance report (hardening + Moltis checks):

```powershell
python -m agent_hum_crawler.main conformance-report --limit 7 --streaming-event-lifecycle pass --tool-registry-source-metadata pass --mcp-disable-builtin-fallback pass --auth-matrix-local-remote-proxy pending --proxy-hardening-configuration pending
```

Generate long-form GraphRAG report from persisted DB evidence (no vector DB required):

```powershell
python -m agent_hum_crawler.main write-report --countries "Madagascar,Mozambique" --disaster-types "cyclone/storm,flood" --limit-cycles 20 --limit-events 60
```

Strict filter mode is enabled by default for reports. If selected filters return zero matches, the report stays filter-faithful and emits a structured "no evidence" report (quality-gate compatible) instead of falling back to another country/disaster window.

Default output path: `reports/report-<timestamp>.md` (project-local).
Generated reports are local artifacts and not committed (`reports/*.md` is ignored; `reports/.gitkeep` is tracked).

Template-driven formatting and section-length limits can be customized in `config/report_template.json`
or overridden with `--report-template`.

`write-report` output includes:
- `llm_used`: `true` only when AI actually produced report sections.
- `report_quality`: pass/fail with citation density, missing section checks, and unsupported-claim checks.

When AI is used, report header includes:
- `AI Assisted: Yes`

Prebuilt templates:

```powershell
# Brief donor update
python -m agent_hum_crawler.main write-report --countries "Madagascar" --disaster-types "cyclone/storm" --use-llm --report-template config/report_template.brief.json

# Detailed analyst brief
python -m agent_hum_crawler.main write-report --countries "Madagascar" --disaster-types "cyclone/storm" --use-llm --report-template config/report_template.detailed.json
```

Template files:
- `config/report_template.json` (default profile)
- `config/report_template.brief.json` (short donor update)
- `config/report_template.detailed.json` (long analyst brief)

Template controls:
- section headings
- section word limits
- max incident highlights
- incident summary/quote length

Enforce report quality gate (section completeness + citation density + unsupported-claim checks):

```powershell
python -m agent_hum_crawler.main write-report --countries "Madagascar" --disaster-types "cyclone/storm" --enforce-report-quality --min-citation-density 0.005
```

Optional LLM final drafting:

```powershell
python -m agent_hum_crawler.main write-report --countries "Madagascar" --disaster-types "cyclone/storm" --use-llm
```

Recommended live run flow:

```powershell
# 1) Collect fresh cycle evidence
python -m agent_hum_crawler.main run-cycle --countries "Madagascar" --disaster-types "cyclone/storm" --limit 15 --include-content

# 2) Generate AI-assisted brief donor report
python -m agent_hum_crawler.main write-report --countries "Madagascar" --disaster-types "cyclone/storm" --limit-cycles 25 --limit-events 20 --use-llm --report-template config/report_template.brief.json

# 3) Generate AI-assisted detailed analyst report
python -m agent_hum_crawler.main write-report --countries "Madagascar" --disaster-types "cyclone/storm" --limit-cycles 25 --limit-events 20 --use-llm --report-template config/report_template.detailed.json
```

Run replay fixture for dry-run QA:

```powershell
python -m agent_hum_crawler.main replay-fixture --fixture tests/fixtures/replay_pakistan_flood_quake.json
```

Start scheduled monitoring (example: one test run and stop):

```powershell
python -m agent_hum_crawler.main start-scheduler --countries "Pakistan" --disaster-types "flood,earthquake" --interval 30 --limit 10 --max-runs 1
```

## Tests

```powershell
pytest -q
```

Local validation gate:

```powershell
.\scripts\local-validate.ps1
```

Linux/macOS:

```bash
./scripts/local-validate.sh
```

This now includes a deterministic E2E regression gate with artifact capture.
Artifacts are written to:
- `artifacts/e2e/<UTC timestamp>/`
- Includes Moltis security/auth evidence artifact:
  - `06_moltis_security_check.json` (auth baseline, auth/proxy matrix, scoped API-key checks)

Skip E2E when needed:

```powershell
.\scripts\local-validate.ps1 -SkipE2E
```

```bash
SKIP_E2E=1 ./scripts/local-validate.sh
```

## Moltis Hook Pack (Post-MVP Phase A)
Project-local hooks are provided under `.moltis/hooks/`:
- `llm-tool-guard` (`BeforeLLMCall`, `AfterLLMCall`)
- `tool-safety-guard` (`BeforeToolCall`)
- `audit-log` (`Command`, `MessageSent`, `AfterToolCall`, `BeforeToolCall`, `AfterLLMCall`)

These are discovered by Moltis as project-local hooks.
Use this command to verify discovery:

```powershell
moltis hooks list --eligible
```

Audit output default:
- `.moltis/logs/hook-audit.jsonl`

## Moltis Security Baseline Check
Run security/auth baseline and evidence checks:

```powershell
python scripts/moltis_security_check.py
```

Optional strict rollout flags:

```powershell
# Enforce proxy posture expectation
python scripts/moltis_security_check.py --expect-behind-proxy true

# Require at least one active scoped API key
python scripts/moltis_security_check.py --require-api-keys
```

## Moltis Hardened Profile (Post-MVP Phase B)
Use the hardened profile template:
- `config/moltis.hardened.example.toml`

Rollout steps:
1. Back up current config:
```powershell
Copy-Item $HOME\.config\moltis\moltis.toml $HOME\.config\moltis\moltis.toml.bak
```
2. Copy template and adapt paths/models for your machine:
```powershell
Copy-Item .\config\moltis.hardened.example.toml $HOME\.config\moltis\moltis.toml
```
3. Restart Moltis and verify:
```powershell
moltis hooks list --eligible
```

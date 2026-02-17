# Pilot Sign-off - Milestone 6

Date: 2026-02-17

## Pilot Scope
- Executed 7 consecutive `run-cycle` pilot runs.
- Runtime filters: countries=`Pakistan`, disaster_types=`flood,earthquake`, interval=`30`, limit=`1`.
- ReliefWeb remained disabled (`RELIEFWEB_ENABLED=false`) during pilot.

## KPI Snapshot
From `quality-report --limit 7`:
- cycles_analyzed: 7
- events_analyzed: 0
- duplicate_rate_estimate: 0.0
- traceable_rate: 1.0

From `source-health --limit 7`:
- Connector failure rates:
  - `ngo_feeds`: 1.0 (IFRC feed returned 403)
  - `government_feeds`: 0.0 (GDACS recovered via parser fallback path)
  - `un_humanitarian_feeds`: 0.0
  - `local_news_feeds`: 0.0

From `hardening-gate --limit 7`:
- status: `warning`
- reason: no events analyzed yet (provisional gate)
- connector_failure_ok: `false` (worst connector failure rate = 1.0)

## Outcome
- Engineering pipeline stability: **PASS**
  - 7-cycle execution completed without blocking runtime errors.
  - Scheduler and cycle persistence remained stable.
  - Health and quality analytics reported correctly.

- Data-quality sign-off: **PARTIAL / PROVISIONAL**
  - No matched disaster events in this pilot window.
  - Hardening gate remains provisional due zero-event sample and persistent NGO feed failure.

## Required Actions Before Final Production Sign-off
1. Enable approved ReliefWeb appname and rerun pilot with live humanitarian coverage.
2. Replace or disable failing NGO feed (`IFRC`) and onboard alternative NGO source.
3. Execute another 7-cycle pilot targeting known active disaster windows or richer filters.
4. Re-run `quality-report`, `source-health`, and `hardening-gate` and confirm gate status `pass`.

## Commands Used
```powershell
python -m agent_hum_crawler.main run-cycle --countries "Pakistan" --disaster-types "flood,earthquake" --interval 30 --limit 1
python -m agent_hum_crawler.main quality-report --limit 7
python -m agent_hum_crawler.main source-health --limit 7
python -m agent_hum_crawler.main hardening-gate --limit 7
```

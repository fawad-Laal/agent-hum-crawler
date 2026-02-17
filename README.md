# Agent HUM Crawler

Dynamic disaster-intelligence monitoring assistant.

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
OPENAI_API_KEY=...
RELIEFWEB_ENABLED=true
RELIEFWEB_APPNAME=your_approved_reliefweb_appname
```

ReliefWeb appname request: https://apidoc.reliefweb.int/parameters#appname
If approval is pending, set `RELIEFWEB_ENABLED=false` to run fallback connectors only.

## Country Source Allowlists
- Active file: `config/country_sources.json`
- Template: `config/country_sources.example.json`

Per-country feeds from this file are merged into connector selection for `run-cycle` and `start-scheduler`.

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

Use saved config for cycle:

```powershell
python -m agent_hum_crawler.main run-cycle --use-saved-config --limit 10
```

Show persisted cycles:

```powershell
python -m agent_hum_crawler.main show-cycles --limit 10
```

Start scheduled monitoring (example: one test run and stop):

```powershell
python -m agent_hum_crawler.main start-scheduler --countries "Pakistan" --disaster-types "flood,earthquake" --interval 30 --limit 10 --max-runs 1
```

## Tests

```powershell
pytest -q
```

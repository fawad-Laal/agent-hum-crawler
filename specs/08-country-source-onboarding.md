# Country Source Onboarding Spec

Date: 2026-02-17
Version: 0.1

## Purpose
Define a repeatable process to onboard country-specific government and local-news sources into the monitoring pipeline.

## File
- Active registry: `config/country_sources.json`
- Template: `config/country_sources.example.json`

## Schema

```json
{
  "global": {
    "government": [{"name": "...", "url": "..."}],
    "un": [{"name": "...", "url": "..."}],
    "ngo": [{"name": "...", "url": "..."}],
    "local_news": [{"name": "...", "url": "..."}]
  },
  "countries": {
    "Pakistan": {
      "government": [{"name": "...", "url": "..."}],
      "un": [{"name": "...", "url": "..."}],
      "ngo": [{"name": "...", "url": "..."}],
      "local_news": [{"name": "...", "url": "..."}]
    }
  }
}
```

## Onboarding Steps Per Country
1. Identify official government alert feeds.
2. Identify 2-5 local news feeds with stable RSS/Atom or structured pages.
3. Add entries under `countries.<CountryName>`.
4. Run one cycle and review output quality.
5. Remove noisy feeds and keep trusted ones.

## Source Quality Rules
- Prefer official agencies and established outlets.
- Avoid sources without timestamps or attribution.
- Keep only feeds with stable access and consistent formatting.
- Revalidate feed health monthly.

## Validation Checklist
- URL resolves and returns feed/content.
- Source emits recent updates.
- Alerts include source URLs and timestamps.
- Duplicate rate remains within project target.

## Operations
- `run-cycle` and `start-scheduler` automatically load registry by monitored countries.
- If registry is missing, built-in default global feeds are used.

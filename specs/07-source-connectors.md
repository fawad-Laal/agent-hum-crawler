# Source Connectors Spec - Disaster Intelligence Agent

Date: 2026-02-17
Version: 0.1 (MVP)

## 1. Purpose
Define how the agent collects information from websites using a reliable, tiered source strategy.

## 2. Source Tiers (Priority)
1. `tier_1_official`
- National government emergency agencies
- National meteorological services
- Geological/seismology agencies
- Civil defense and disaster management authorities

2. `tier_2_humanitarian`
- ReliefWeb (required)
- UN organizations and OCHA-related updates
- Major humanitarian NGOs

3. `tier_3_reputable_news`
- Trusted international and local news outlets with clear editorial standards

4. `tier_4_social_supporting`
- Social media posts only as supporting signals, never sole confirmation

## 3. Required MVP Connectors
- `reliefweb`: baseline humanitarian source
- `government_feeds`: country-specific official sources
- `un_humanitarian_feeds`: UN/OCHA-style updates
- `ngo_feeds`: selected NGOs relevant to crisis response
- `local_news_feeds`: country-specific local news providers

## 4. Collection Methods
For each connector, preferred method order:
1. Official API (if available)
2. RSS/Atom feed
3. Static page parsing
4. Browser-rendered extraction (fallback for JS-heavy pages)

Collection mode must be two-stage:
1. `link-level` discovery:
- collect URL, title, timestamp, source metadata quickly.
2. `content-level` extraction:
- fetch article/body text for classification and verification.
- if page links to primary documents (PDF/HTML bulletin), extract key content from those documents too.
- keep full scraping targeted to matched items only (avoid scraping everything).

Connector output must map to a common raw item shape:

```json
{
  "connector": "reliefweb",
  "source_type": "humanitarian",
  "url": "https://example.org/post/123",
  "title": "Flood warning update",
  "published_at": "2026-02-17T15:10:00Z",
  "country_candidates": ["Pakistan"],
  "text": "...",
  "content_mode": "content-level",
  "content_sources": [
    {"type": "web_page", "url": "https://example.org/post/123"},
    {"type": "document_pdf", "url": "https://example.org/post/123/report.pdf"}
  ],
  "language": "en"
}
```

## 5. Country/Disaster Filtering Logic
Given user runtime config:
- `countries`
- `disaster_types`
- optional `subregions`

Filter raw items by:
1. Country mention match (exact + alias dictionary)
2. Disaster keyword match (type synonyms)
3. Recency window (new/updated since last cycle)

Example disaster keyword groups:
- `cyclone/storm`: cyclone, hurricane, typhoon, tropical storm, severe storm
- `flood`: flood, flash flood, inundation, overflow
- `earthquake`: earthquake, seismic, tremor, aftershock
- `conflict emergency`: conflict, displacement, violence, armed clashes

## 6. Verification and Confidence Rules
- High confidence requires at least one tier 1 or corroborated tier 2 source.
- Medium confidence allowed with single tier 2 or multiple tier 3 corroborations.
- Low confidence for single tier 3 signal or any uncorroborated tier 4 signal.
- Never mark high confidence from only social content.

## 7. Deduplication Across Sources
Use `event_id` and similarity matching across:
- normalized location
- disaster type
- time window
- headline/summary similarity

If multiple sources report same event:
- merge sources into one event record
- keep strongest source tier for confidence computation

## 8. Local News Policy
Local news is required, but must be quality-controlled:
- Maintain allowlist per country.
- Reject sources with unclear attribution or repeated misinformation.
- Require corroboration for high-impact claims.

## 9. Failure Handling
- If one connector fails, continue cycle with remaining connectors.
- Record connector failure with timestamp and error class.
- If all tier 1 and tier 2 connectors fail, downgrade confidence and label output "limited verification".

## 10. Initial Connector Registry Template

```json
{
  "connectors": [
    {"id": "reliefweb", "tier": "tier_2_humanitarian", "enabled": true, "method": "api_or_feed"},
    {"id": "government_feeds", "tier": "tier_1_official", "enabled": true, "method": "feed_or_parse"},
    {"id": "un_humanitarian_feeds", "tier": "tier_2_humanitarian", "enabled": true, "method": "feed_or_parse"},
    {"id": "ngo_feeds", "tier": "tier_2_humanitarian", "enabled": true, "method": "feed_or_parse"},
    {"id": "local_news_feeds", "tier": "tier_3_reputable_news", "enabled": true, "method": "feed_parse_browser_fallback"}
  ]
}
```

## 11. Acceptance Criteria
- ReliefWeb is included and active.
- At least one government and one local news connector are active per monitored country.
- Every alert includes at least one source URL and timestamp.
- High/critical alerts are corroborated by reliable tiers when available.

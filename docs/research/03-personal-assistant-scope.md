# Personal Assistant Scope - Emergency and Disaster Intelligence

Date: 2026-02-17

## Objective
Build a Moltis-based personal assistant that continuously collects and summarizes online information about disasters and specific emergencies, then delivers actionable alerts.

## Primary Use Cases
- Monitor disaster events in selected regions (floods, earthquakes, storms, wildfires, conflict-related emergencies).
- Detect major updates quickly (new warnings, evacuation orders, infrastructure impacts, casualty reports).
- Produce short situation summaries with source links and confidence levels.
- Send urgent alerts in Moltis chat.

## In Scope (MVP)
- Scheduled web/news monitoring for selected topics and locations.
- Source triage and deduplication (avoid repeated alerts).
- Alert severity classification: `low`, `medium`, `high`, `critical`.
- Brief output format:
  - what happened
  - where and when
  - why it matters
  - what changed since last update
  - links to sources

## Out of Scope (for now)
- Automated public posting to social media.
- Medical or legal instructions beyond sourced guidance.
- Autonomous decision making (no direct emergency actions without human approval).

## Data Sources (Priority Order)
1. Official agencies and warnings (government emergency management, meteorological, geological services).
2. International humanitarian/relief sources (UN agencies, Red Cross/Red Crescent, major NGOs).
3. Reputable wire/news sources.
4. Social media only as supporting evidence, never as sole confirmation.

## Geographic and Topic Filters
Dynamic watchlist (user-defined at setup and editable later):
- Countries/regions: one or many (required).
- Disaster types: any subset of `earthquake`, `flood`, `cyclone/storm`, `wildfire`, `landslide`, `heatwave`, `conflict emergency`.
- Optional city/province refinement per country.
- Optional custom keywords with local spellings and aliases.

## User Input Model (Dynamic Agent Configuration)
The agent should start from user input and build filters dynamically.

Required inputs:
- `countries`: list of countries to monitor.
- `disaster_types`: list of selected disaster categories.
- `check_interval_minutes`: polling interval in minutes.

Optional inputs:
- `subregions`: map of country to city/province list.
- `priority_sources`: preferred domains/feeds.
- `quiet_hours_local`: do-not-disturb window for non-critical alerts.

Example config payload:

```json
{
  "countries": ["Pakistan", "Bangladesh"],
  "disaster_types": ["cyclone/storm", "flood", "earthquake"],
  "check_interval_minutes": 30,
  "subregions": {
    "Pakistan": ["Sindh", "Balochistan"],
    "Bangladesh": ["Chattogram"]
  }
}
```

## Alerting Rules (Initial)
- `critical`: official evacuation order, major casualty updates, severe infrastructure failure, or imminent life-safety risk.
- `high`: active major incident with confirmed multi-source reporting.
- `medium`: verified developing incident with limited impact data.
- `low`: monitoring signals or early warnings with limited confirmation.

Send alert when:
- severity is `high` or `critical`, or
- a `medium` event has a meaningful update compared to previous report.

## Reliability and Safety Rules
- Never claim certainty with a single unverified source.
- Label every item with confidence: `low`, `medium`, `high`.
- Include timestamps and source links for every report.
- Separate facts from inference explicitly.
- Add note: "For life-threatening situations, follow local emergency authorities immediately."

## Output Templates

### Quick alert (1-3 lines)
- `Severity`: high
- `Update`: Flood warning expanded to [area], roads closed.
- `Source`: [link] (updated [time])

### Situation summary (daily or on-demand)
- Top 3 active emergencies by severity
- New events in last 24h
- Escalations/de-escalations since prior summary
- Source table with links

## Moltis Implementation Plan (MVP)
1. Configure one primary provider for reasoning/summarization.
2. Enable tool use with cautious permissions.
3. Build an intake prompt that asks user for countries, disaster types, and check interval.
4. Create a monitoring workflow prompt that consumes these dynamic inputs.
5. Store previous alert hashes to prevent duplicates.
6. Send alerts to Moltis chat only (phase 1).
7. Save event history in memory for trend comparisons.

## Prompt Starter (for Moltis)
"Ask the user to define countries, disaster types, and check interval in minutes. Then monitor online sources for those filters. Return only verified updates with source URLs, timestamps, severity, and confidence. Highlight what changed since last report and suppress duplicates. Send alerts in Moltis chat."

## Decisions Needed from User
- Exact countries to monitor (and optional cities/provinces).
- Disaster types to include.
- Update interval in minutes.
- Preferred summary style (brief tactical vs detailed analytical).

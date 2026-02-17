# Moltis Config Template - Dynamic Disaster Monitoring Agent

Date: 2026-02-17

## Goal
Provide a practical configuration blueprint to run a dynamic emergency/disaster intelligence assistant in Moltis, with Moltis-chat alerts only.

## Assumptions
- Moltis is installed and runnable (`moltis --version` works).
- A provider is connected (Ollama, OpenAI Codex, or GitHub Copilot).
- Monitoring criteria are user-defined at runtime (countries, disaster types, interval).

## 1) Core Runtime Config (`~/.config/moltis/moltis.toml`)

Use this as a starting template and adjust to your environment.

```toml
# Basic gateway settings
[gateway]
host = "127.0.0.1"
port = 13131

# Keep memory enabled so monitoring history can be compared across cycles
[memory]
enabled = true

# Optional: keep local provider block only if you use GGUF local models
# If you do not use GGUF, leave this disabled or remove to reduce startup noise
[providers.local]
enabled = false
models = []

# Optional: enable Ollama if you use locally hosted models via Ollama
[providers.ollama]
enabled = true
base_url = "http://localhost:11434"

# Recommended safety posture for an online-monitoring assistant
[tools]
enabled = true

# Keep shell tool conservative for MVP
[tools.shell]
enabled = true
mode = "read-mostly"

# Browser/web research support
[tools.browser]
enabled = true

# Future channel options (Telegram disabled for phase 1)
[channels.telegram]
enabled = false
```

Note:
- Exact key names can vary by Moltis version. If `moltis doctor` reports unknown keys, keep behavior intent the same and adapt to reported schema.

## 2) Agent Runtime State (JSON)

Persist this object in memory/session notes and update it via intake prompt.

```json
{
  "countries": [],
  "disaster_types": [],
  "check_interval_minutes": 30,
  "subregions": {},
  "priority_sources": [],
  "quiet_hours_local": null,
  "last_cycle_hashes": [],
  "last_run_at": null
}
```

## 3) First-Run Intake Procedure

1. Run intake prompt from `docs/research/04-agent-prompts.md`.
2. Collect required fields:
   - `countries`
   - `disaster_types`
   - `check_interval_minutes`
3. Confirm JSON with user.
4. Start monitoring only after explicit confirmation.

## 4) Monitoring Cycle Procedure

For each cycle:
1. Search trusted sources for matching country/disaster filters.
2. Normalize findings into a standard event shape:
   - `event_id`, `country`, `subregion`, `disaster_type`, `severity`, `confidence`, `summary`, `sources`, `updated_at`
3. Compare with previous cycle (`last_cycle_hashes`) for dedupe/change detection.
4. Send Moltis alerts only for:
   - all `high` and `critical`
   - `medium` with meaningful change
5. Save cycle output summary and update state.

## 5) Example User Config (MVP)

```json
{
  "countries": ["Pakistan", "Bangladesh"],
  "disaster_types": ["cyclone/storm", "flood", "earthquake", "conflict emergency"],
  "check_interval_minutes": 30,
  "subregions": {
    "Pakistan": ["Sindh", "Balochistan"],
    "Bangladesh": ["Chattogram"]
  }
}
```

## 6) Operations Commands

Use these while iterating configuration.

```powershell
moltis --version
moltis doctor
moltis
```

## 7) Phase 1 Acceptance Criteria

- User can define countries/disaster types/interval at runtime.
- Agent performs repeated monitoring cycles using those inputs.
- Duplicate alerts are suppressed.
- Alerts appear in Moltis chat in the defined concise format.
- Each alert includes timestamp, severity, confidence, and source URLs.

## 8) Phase 2 (Later)

- Add Telegram channel delivery.
- Add source-specific weighting.
- Add daily digest and weekly trend summaries.
- Add escalation-specific routing rules.

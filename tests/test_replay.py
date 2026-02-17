from pathlib import Path

from agent_hum_crawler.replay import run_replay_fixture


def test_replay_fixture_output_contract() -> None:
    fixture = Path("tests/fixtures/replay_pakistan_flood_quake.json")
    result = run_replay_fixture(fixture)

    assert len(result.events) >= 2
    assert "critical_high_alerts" in result.alerts_contract
    assert "medium_updates" in result.alerts_contract
    assert "watchlist_signals" in result.alerts_contract
    assert "source_log" in result.alerts_contract
    assert "next_check_time" in result.alerts_contract

    # Flood event should be corroborated (gov + local news)
    flood_events = [e for e in result.events if e.disaster_type == "flood"]
    assert flood_events
    assert flood_events[0].corroboration_sources >= 2

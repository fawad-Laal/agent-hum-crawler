from agent_hum_crawler.config import RuntimeConfig
from agent_hum_crawler.cycle import CycleResult
from agent_hum_crawler.pilot import run_pilot


def test_run_pilot_runs_requested_cycles(monkeypatch) -> None:
    config = RuntimeConfig(
        countries=["Madagascar"],
        disaster_types=["cyclone/storm"],
        check_interval_minutes=30,
    )
    calls = {"count": 0}

    def fake_run_cycle(runtime_config, limit, include_content):
        assert runtime_config == config
        assert limit == 5
        assert include_content is True
        calls["count"] += 1
        return CycleResult(
            cycle_id=calls["count"],
            summary="ok",
            connector_count=2,
            raw_item_count=3,
            event_count=1,
            events=[],
            connector_metrics=[],
            llm_enrichment={"enabled": False, "enriched_count": 0, "fallback_count": 1},
        )

    monkeypatch.setattr(
        "agent_hum_crawler.pilot.build_quality_report",
        lambda limit_cycles: {
            "cycles_analyzed": limit_cycles,
            "events_analyzed": 3,
            "duplicate_rate_estimate": 0.0,
            "traceable_rate": 1.0,
        },
    )
    monkeypatch.setattr(
        "agent_hum_crawler.pilot.build_source_health_report",
        lambda limit_cycles: {
            "cycles_analyzed": limit_cycles,
            "connectors": [{"connector": "un", "failure_rate": 0.0}],
            "sources": [],
        },
    )

    result = run_pilot(
        config=config,
        cycles=3,
        limit=5,
        include_content=True,
        run_cycle_fn=fake_run_cycle,
    )

    assert calls["count"] == 3
    assert result["cycles_completed"] == 3
    assert result["hardening_gate"]["status"] == "pass"


def test_run_pilot_supports_sleep_between_cycles() -> None:
    config = RuntimeConfig(
        countries=["Mozambique"],
        disaster_types=["flood"],
        check_interval_minutes=30,
    )
    waits = []

    def fake_run_cycle(runtime_config, limit, include_content):
        return CycleResult(
            cycle_id=1,
            summary="ok",
            connector_count=1,
            raw_item_count=1,
            event_count=0,
            events=[],
            connector_metrics=[],
            llm_enrichment={"enabled": False, "enriched_count": 0, "fallback_count": 0},
        )

    def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    result = run_pilot(
        config=config,
        cycles=4,
        limit=2,
        include_content=False,
        sleep_seconds=0.5,
        run_cycle_fn=fake_run_cycle,
        sleep_fn=fake_sleep,
    )

    assert waits == [0.5, 0.5, 0.5]
    assert result["cycles_completed"] == 4

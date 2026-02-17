from agent_hum_crawler.hardening import evaluate_hardening_gate


def test_hardening_gate_pass() -> None:
    quality = {
        "cycles_analyzed": 5,
        "events_analyzed": 20,
        "duplicate_rate_estimate": 0.05,
        "traceable_rate": 1.0,
    }
    source_health = {
        "connectors": [
            {"connector": "a", "failure_rate": 0.2},
            {"connector": "b", "failure_rate": 0.1},
        ]
    }

    result = evaluate_hardening_gate(quality, source_health)
    assert result["status"] == "pass"
    assert all(result["checks"].values())


def test_hardening_gate_fail() -> None:
    quality = {
        "cycles_analyzed": 5,
        "events_analyzed": 20,
        "duplicate_rate_estimate": 0.30,
        "traceable_rate": 0.80,
    }
    source_health = {
        "connectors": [
            {"connector": "a", "failure_rate": 0.9},
        ]
    }

    result = evaluate_hardening_gate(quality, source_health)
    assert result["status"] == "fail"
    assert not all(result["checks"].values())

from agent_hum_crawler.hardening import evaluate_hardening_gate, evaluate_llm_quality_gate


def test_hardening_gate_pass() -> None:
    quality = {
        "cycles_analyzed": 5,
        "events_analyzed": 20,
        "duplicate_rate_estimate": 0.05,
        "traceable_rate": 1.0,
        "llm_attempted_events": 0,
        "llm_enrichment_rate": 0.0,
        "citation_coverage_rate": 0.0,
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
        "llm_attempted_events": 10,
        "llm_enrichment_rate": 0.05,
        "citation_coverage_rate": 0.50,
    }
    source_health = {
        "connectors": [
            {"connector": "a", "failure_rate": 0.9},
        ]
    }

    result = evaluate_hardening_gate(quality, source_health)
    assert result["status"] == "fail"
    assert not all(result["checks"].values())


def test_llm_quality_gate_not_applicable() -> None:
    report = evaluate_llm_quality_gate(
        {"llm_attempted_events": 0, "llm_enrichment_rate": 0.0, "citation_coverage_rate": 0.0}
    )
    assert report["status"] == "warning"
    assert report["checks"]["llm_enrichment_rate_ok"] is True
    assert report["checks"]["citation_coverage_ok"] is True


def test_llm_quality_gate_fail() -> None:
    report = evaluate_llm_quality_gate(
        {
            "llm_attempted_events": 20,
            "llm_enrichment_rate": 0.05,
            "citation_coverage_rate": 0.80,
            "llm_provider_error_count": 1,
            "llm_validation_fail_count": 2,
        },
        min_llm_enrichment_rate=0.10,
        min_citation_coverage_rate=0.95,
    )
    assert report["status"] == "fail"
    assert report["checks"]["llm_enrichment_rate_ok"] is False
    assert report["checks"]["citation_coverage_ok"] is False

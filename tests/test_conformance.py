from agent_hum_crawler.conformance import evaluate_moltis_conformance


def test_conformance_pass_when_all_checks_and_hardening_pass() -> None:
    result = evaluate_moltis_conformance(
        hardening_status="pass",
        checks={
            "streaming_event_lifecycle": "pass",
            "tool_registry_source_metadata": "pass",
            "mcp_disable_builtin_fallback": "pass",
        },
    )

    assert result["status"] == "pass"
    assert result["summary"]["failed"] == []
    assert result["summary"]["pending"] == []


def test_conformance_fails_on_any_failed_check() -> None:
    result = evaluate_moltis_conformance(
        hardening_status="pass",
        checks={
            "streaming_event_lifecycle": "fail",
            "tool_registry_source_metadata": "pass",
        },
    )

    assert result["status"] == "fail"
    assert "streaming_event_lifecycle" in result["summary"]["failed"]


def test_conformance_warns_when_hardening_not_pass() -> None:
    result = evaluate_moltis_conformance(
        hardening_status="warning",
        checks={
            "streaming_event_lifecycle": "pass",
            "tool_registry_source_metadata": "pass",
        },
    )

    assert result["status"] == "warning"
    assert "Hardening gate is not pass yet" in result["reason"]

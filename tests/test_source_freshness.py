from agent_hum_crawler.source_freshness import evaluate_freshness, update_source_state


def test_evaluate_freshness_stale() -> None:
    freshness = evaluate_freshness("2020-01-01T00:00:00+00:00", 30)
    assert freshness.status == "stale"
    assert freshness.is_stale is True


def test_update_source_state_resets_streak_when_fresh() -> None:
    state = {"sources": {"https://example.com/feed": {"stale_streak": 3}}}
    row = update_source_state(
        state,
        source_url="https://example.com/feed",
        latest_published_at="2026-02-19T00:00:00+00:00",
        freshness_status="fresh",
        status="ok",
    )
    assert int(row["stale_streak"]) == 0

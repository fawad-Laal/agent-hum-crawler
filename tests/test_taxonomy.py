from agent_hum_crawler.taxonomy import infer_disaster_type, match_with_reason


def test_conflict_emergency_requires_stronger_signals() -> None:
    text = (
        "AU Summit annual ritual without tangible progress in Addis Abeba. "
        "Leaders discussed diplomacy and reforms."
    )
    inferred = infer_disaster_type(text, ["conflict emergency"])
    assert inferred is None


def test_conflict_emergency_matches_with_conflict_and_humanitarian_impact() -> None:
    text = (
        "Armed clashes intensified in the region, with multiple attacks reported. "
        "Thousands were displaced and humanitarian agencies reported casualties."
    )
    inferred = infer_disaster_type(text, ["conflict emergency"])
    assert inferred == "conflict emergency"


def test_match_with_reason_country_miss() -> None:
    ok, reason = match_with_reason(
        title="Flood alert in Peru",
        text="Flash flooding expected this week",
        country_candidates=["Peru"],
        countries=["Mozambique"],
        disaster_types=["flood"],
    )
    assert ok is False
    assert reason == "country_miss"


def test_match_with_reason_age_filtered() -> None:
    ok, reason = match_with_reason(
        title="Mozambique flood update",
        text="Heavy flood affected multiple districts.",
        country_candidates=["Mozambique"],
        countries=["Mozambique"],
        disaster_types=["flood"],
        published_at="2025-01-01T00:00:00+00:00",
        max_age_days=10,
    )
    assert ok is False
    assert reason == "age_filtered"

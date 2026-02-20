from pydantic import ValidationError

from agent_hum_crawler.config import RuntimeConfig


def test_valid_config() -> None:
    cfg = RuntimeConfig(
        countries=["Pakistan"],
        disaster_types=["flood", "earthquake"],
        check_interval_minutes=30,
    )
    assert cfg.check_interval_minutes == 30


def test_invalid_interval() -> None:
    try:
        RuntimeConfig(
            countries=["Pakistan"],
            disaster_types=["flood"],
            check_interval_minutes=1,
        )
        assert False, "Expected ValidationError"
    except ValidationError as exc:
        assert "greater than or equal" in str(exc)


def test_invalid_disaster_type() -> None:
    try:
        RuntimeConfig(
            countries=["Pakistan"],
            disaster_types=["tornado"],
            check_interval_minutes=30,
        )
        assert False, "Expected ValidationError"
    except ValidationError as exc:
        assert "Invalid disaster type" in str(exc)


def test_disaster_type_aliases_are_normalized() -> None:
    cfg = RuntimeConfig(
        countries=["Mozambique"],
        disaster_types=["Floods", "Cyclones", "Heat Waves"],
        check_interval_minutes=30,
    )
    assert cfg.disaster_types == ["flood", "cyclone/storm", "heatwave"]


def test_missing_country() -> None:
    try:
        RuntimeConfig(
            countries=[],
            disaster_types=["flood"],
            check_interval_minutes=30,
        )
        assert False, "Expected ValidationError"
    except ValidationError as exc:
        assert "countries" in str(exc)

"""Interactive intake flow for runtime configuration."""

from __future__ import annotations

import json
from typing import List

from pydantic import ValidationError

from .config import ALLOWED_DISASTER_TYPES, RuntimeConfig


def _parse_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def run_intake() -> RuntimeConfig:
    print("Configure monitoring before starting.")
    countries = _parse_csv(input("Countries (comma-separated): "))
    disaster_types = _parse_csv(
        input(
            "Disaster types (comma-separated from: "
            + ", ".join(sorted(ALLOWED_DISASTER_TYPES))
            + "): "
        )
    )
    interval_raw = input("Check interval (minutes): ").strip()

    try:
        interval = int(interval_raw)
    except ValueError as exc:
        raise ValueError("check_interval_minutes must be an integer") from exc

    try:
        cfg = RuntimeConfig(
            countries=countries,
            disaster_types=disaster_types,
            check_interval_minutes=interval,
        )
    except ValidationError as exc:
        print("\nConfiguration errors:")
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "invalid value")
            print(f"- {loc}: {msg}")
        raise ValueError("Invalid runtime configuration.") from exc

    print("\nConfiguration JSON:")
    print(json.dumps(cfg.model_dump(), indent=2))
    confirm = input("Start monitoring with this configuration? (yes/no): ").strip().lower()
    if confirm not in {"y", "yes"}:
        raise ValueError("Configuration not confirmed.")

    return cfg

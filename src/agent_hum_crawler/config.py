"""Runtime configuration schema and validation using pydantic."""

from __future__ import annotations

import re
from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_DISASTER_TYPES = {
    "earthquake",
    "flood",
    "cyclone/storm",
    "wildfire",
    "landslide",
    "heatwave",
    "conflict emergency",
}

_DISASTER_TYPE_ALIAS_MAP = {
    "earthquake": "earthquake",
    "earthquakes": "earthquake",
    "quake": "earthquake",
    "quakes": "earthquake",
    "seismic": "earthquake",
    "flood": "flood",
    "floods": "flood",
    "flooding": "flood",
    "cyclone/storm": "cyclone/storm",
    "cyclone storm": "cyclone/storm",
    "cyclone": "cyclone/storm",
    "cyclones": "cyclone/storm",
    "storm": "cyclone/storm",
    "storms": "cyclone/storm",
    "tropical cyclone": "cyclone/storm",
    "hurricane": "cyclone/storm",
    "typhoon": "cyclone/storm",
    "wildfire": "wildfire",
    "wildfires": "wildfire",
    "fire": "wildfire",
    "fires": "wildfire",
    "bushfire": "wildfire",
    "bushfires": "wildfire",
    "landslide": "landslide",
    "landslides": "landslide",
    "mudslide": "landslide",
    "mudslides": "landslide",
    "heatwave": "heatwave",
    "heatwaves": "heatwave",
    "heat wave": "heatwave",
    "heat waves": "heatwave",
    "conflict emergency": "conflict emergency",
    "complex emergency": "conflict emergency",
    "conflict": "conflict emergency",
    "conflicts": "conflict emergency",
}


def canonicalize_disaster_type(value: str) -> str | None:
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned in ALLOWED_DISASTER_TYPES:
        return cleaned
    key = re.sub(r"\s+", " ", re.sub(r"[_/\-]+", " ", cleaned)).strip()
    return _DISASTER_TYPE_ALIAS_MAP.get(key)


def normalize_disaster_types(values: List[str], *, strict: bool = False) -> List[str]:
    normalized: list[str] = []
    invalid: list[str] = []
    for value in values:
        canonical = canonicalize_disaster_type(value)
        if canonical:
            if canonical not in normalized:
                normalized.append(canonical)
        else:
            cleaned = value.strip().lower()
            if cleaned:
                invalid.append(cleaned)
    if strict and invalid:
        raise ValueError(f"Invalid disaster type(s): {', '.join(sorted(set(invalid)))}")
    return normalized


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    countries: List[str] = Field(min_length=1)
    disaster_types: List[str] = Field(min_length=1)
    check_interval_minutes: int = Field(ge=5, le=1440)
    subregions: Dict[str, List[str]] = Field(default_factory=dict)
    priority_sources: List[str] = Field(default_factory=list)
    quiet_hours_local: str | None = None
    max_item_age_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("countries")
    @classmethod
    def validate_countries(cls, value: List[str]) -> List[str]:
        cleaned = [c for c in (v.strip() for v in value) if c]
        if not cleaned:
            raise ValueError("At least one country is required.")
        return cleaned

    @field_validator("disaster_types")
    @classmethod
    def validate_disaster_types(cls, value: List[str]) -> List[str]:
        cleaned = normalize_disaster_types(value, strict=True)
        if not cleaned:
            raise ValueError("At least one disaster type is required.")
        return cleaned

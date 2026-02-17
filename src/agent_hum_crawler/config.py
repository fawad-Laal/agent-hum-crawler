"""Runtime configuration schema and validation using pydantic."""

from __future__ import annotations

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


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    countries: List[str] = Field(min_length=1)
    disaster_types: List[str] = Field(min_length=1)
    check_interval_minutes: int = Field(ge=5, le=1440)
    subregions: Dict[str, List[str]] = Field(default_factory=dict)
    priority_sources: List[str] = Field(default_factory=list)
    quiet_hours_local: str | None = None

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
        cleaned = [v.strip().lower() for v in value if v and v.strip()]
        if not cleaned:
            raise ValueError("At least one disaster type is required.")
        invalid = sorted(set(cleaned) - ALLOWED_DISASTER_TYPES)
        if invalid:
            raise ValueError(f"Invalid disaster type(s): {', '.join(invalid)}")
        return cleaned

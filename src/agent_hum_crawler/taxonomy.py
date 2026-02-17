"""Disaster taxonomy and matching helpers."""

from __future__ import annotations

from typing import Dict, Iterable, List

DISASTER_KEYWORDS: Dict[str, List[str]] = {
    "earthquake": ["earthquake", "seismic", "tremor", "aftershock"],
    "flood": ["flood", "flash flood", "inundation", "overflow"],
    "cyclone/storm": ["cyclone", "storm", "hurricane", "typhoon", "tropical storm"],
    "wildfire": ["wildfire", "forest fire", "bushfire"],
    "landslide": ["landslide", "mudslide", "rockslide"],
    "heatwave": ["heatwave", "extreme heat", "high temperature"],
    "conflict emergency": ["conflict", "displacement", "armed clashes", "violence"],
}


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def matches_country(text: str, countries: Iterable[str]) -> bool:
    haystack = normalize_text(text)
    return any(normalize_text(country) in haystack for country in countries)


def infer_disaster_type(text: str, allowed_types: Iterable[str]) -> str | None:
    haystack = normalize_text(text)
    for disaster_type in allowed_types:
        keywords = DISASTER_KEYWORDS.get(disaster_type, [disaster_type])
        if any(normalize_text(keyword) in haystack for keyword in keywords):
            return disaster_type
    return None


def matches_config(
    title: str,
    text: str,
    country_candidates: List[str],
    countries: List[str],
    disaster_types: List[str],
) -> bool:
    combined = " ".join([title, text, " ".join(country_candidates)])
    if not matches_country(combined, countries):
        return False
    return infer_disaster_type(combined, disaster_types) is not None

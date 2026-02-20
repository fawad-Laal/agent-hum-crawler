"""Disaster taxonomy and matching helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Dict, Iterable, List

from .time_utils import parse_published_datetime

DISASTER_KEYWORDS: Dict[str, List[str]] = {
    "earthquake": ["earthquake", "seismic", "tremor", "aftershock"],
    "flood": ["flood", "flash flood", "inundation", "overflow"],
    "cyclone/storm": ["cyclone", "storm", "hurricane", "typhoon", "tropical storm"],
    "wildfire": ["wildfire", "forest fire", "bushfire"],
    "landslide": ["landslide", "mudslide", "rockslide"],
    "heatwave": ["heatwave", "extreme heat", "high temperature"],
    "conflict emergency": ["conflict", "displacement", "armed clashes", "violence"],
    "epidemic/disease outbreak": [
        "epidemic", "disease outbreak", "outbreak", "pandemic",
        "cholera", "measles", "ebola", "malaria", "dengue",
        "disease", "infectious", "meningitis", "polio",
        "avian flu", "bird flu", "yellow fever", "plague",
        "public health emergency", "health emergency",
    ],
    "drought": [
        "drought", "dry spell", "water scarcity", "famine",
        "food insecurity", "crop failure", "water shortage",
        "desertification", "arid",
    ],
    "volcanic eruption": [
        "volcano", "volcanic", "eruption", "lava", "ash cloud",
        "pyroclastic", "magma",
    ],
    "tsunami": ["tsunami", "tidal wave"],
}

CONFLICT_STRONG_KEYWORDS = [
    "armed conflict",
    "armed clashes",
    "fighting",
    "war",
    "militia",
    "airstrike",
    "bombing",
    "shelling",
    "insurgency",
    "attack",
    "attacks",
    "violence",
]

CONFLICT_IMPACT_KEYWORDS = [
    "displaced",
    "displacement",
    "idp",
    "refugee",
    "humanitarian",
    "casualties",
    "killed",
    "injured",
    "deaths",
    "food insecurity",
    "protection",
]


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def matches_country(text: str, countries: Iterable[str]) -> bool:
    haystack = normalize_text(text)
    for country in countries:
        term = normalize_text(country)
        if not term:
            continue
        # Word-boundary match — prevents "Niger" matching "Nigeria" etc.
        pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
        if re.search(pattern, haystack):
            return True
    return False


def infer_disaster_type(text: str, allowed_types: Iterable[str]) -> str | None:
    haystack = normalize_text(text)
    for disaster_type in allowed_types:
        if disaster_type == "conflict emergency":
            if _is_conflict_emergency(haystack):
                return disaster_type
            continue
        keywords = DISASTER_KEYWORDS.get(disaster_type, [disaster_type])
        if any(_contains_keyword(haystack, keyword) for keyword in keywords):
            return disaster_type
    return None


def _contains_keyword(text: str, keyword: str) -> bool:
    term = normalize_text(keyword)
    if not term:
        return False
    # Word-boundary style check for safer matching on short terms.
    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return re.search(pattern, text) is not None


def _is_conflict_emergency(haystack: str) -> bool:
    strong_hits = sum(1 for k in CONFLICT_STRONG_KEYWORDS if _contains_keyword(haystack, k))
    impact_hits = sum(1 for k in CONFLICT_IMPACT_KEYWORDS if _contains_keyword(haystack, k))
    return (strong_hits >= 1 and impact_hits >= 1) or strong_hits >= 2


def matches_config(
    title: str,
    text: str,
    country_candidates: List[str],
    countries: List[str],
    disaster_types: List[str],
) -> bool:
    ok, _ = match_with_reason(
        title=title,
        text=text,
        country_candidates=country_candidates,
        countries=countries,
        disaster_types=disaster_types,
    )
    return ok


def match_with_reason(
    *,
    title: str,
    text: str,
    country_candidates: List[str],
    countries: List[str],
    disaster_types: List[str],
    published_at: str | None = None,
    max_age_days: int | None = None,
) -> tuple[bool, str]:
    combined = " ".join([title, text, " ".join(country_candidates)])
    if not matches_country(combined, countries):
        return False, "country_miss"
    if infer_disaster_type(combined, disaster_types) is None:
        return False, "hazard_miss"
    if max_age_days:
        dt = parse_published_datetime(published_at)
        if dt is not None:
            now = datetime.now(UTC)
            if dt <= now and (now - dt) > timedelta(days=max_age_days):
                return False, "age_filtered"
    return True, "matched"

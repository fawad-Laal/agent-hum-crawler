"""Dedupe and change detection for aggregated source items."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List

from .models import ProcessedEvent, RawSourceItem
from .taxonomy import infer_disaster_type, matches_country, normalize_text


@dataclass
class DedupeResult:
    events: List[ProcessedEvent]
    current_hashes: List[str]


@dataclass
class CandidateItem:
    item: RawSourceItem
    country: str
    disaster_type: str


SEVERITY_LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}
SEVERITY_BY_LEVEL = {v: k for k, v in SEVERITY_LEVELS.items()}
SOURCE_TYPE_RANK = {"social": 0, "news": 1, "humanitarian": 2, "official": 3}


def _event_hash(item: RawSourceItem, country: str, disaster_type: str, representative_title: str | None = None) -> str:
    title = representative_title or item.title
    canonical = "|".join(
        [
            normalize_text(country),
            normalize_text(disaster_type),
            normalize_text(title),
            normalize_text(item.published_at or ""),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _severity_from_text(text: str) -> str:
    haystack = normalize_text(text)
    if any(k in haystack for k in ["evacuation", "mass casualty", "catastrophic", "state of emergency"]):
        return "critical"
    if any(k in haystack for k in ["fatal", "deaths", "major", "severe", "widespread"]):
        return "high"
    if any(k in haystack for k in ["warning", "alert", "watch", "advisory"]):
        return "medium"
    return "low"


def _confidence_from_source(source_type: str) -> str:
    if source_type == "official":
        return "high"
    if source_type == "humanitarian":
        return "medium"
    if source_type == "news":
        return "medium"
    return "low"


def _find_similar_status(title: str, existing: Dict[str, ProcessedEvent]) -> str:
    normalized = normalize_text(title)
    for prev in existing.values():
        score = SequenceMatcher(a=normalized, b=normalize_text(prev.title)).ratio()
        if score >= 0.92:
            return "updated"
    return "new"


def _cluster_candidates(candidates: List[CandidateItem]) -> List[List[CandidateItem]]:
    clusters: List[List[CandidateItem]] = []

    for candidate in candidates:
        placed = False
        title = normalize_text(candidate.item.title)
        for cluster in clusters:
            pivot = cluster[0]
            if candidate.country != pivot.country or candidate.disaster_type != pivot.disaster_type:
                continue
            score = SequenceMatcher(a=title, b=normalize_text(pivot.item.title)).ratio()
            if score >= 0.90:
                cluster.append(candidate)
                placed = True
                break
        if not placed:
            clusters.append([candidate])

    return clusters


def _pick_primary(cluster: List[CandidateItem]) -> CandidateItem:
    def score(c: CandidateItem) -> tuple[int, int]:
        return (SOURCE_TYPE_RANK.get(c.item.source_type, 0), len(c.item.text or ""))

    return sorted(cluster, key=score, reverse=True)[0]


def _calibrate_severity_and_confidence(cluster: List[CandidateItem]) -> tuple[str, str]:
    distinct_connectors = len({c.item.connector for c in cluster})
    distinct_source_types = len({c.item.source_type for c in cluster})
    strongest_rank = max(SOURCE_TYPE_RANK.get(c.item.source_type, 0) for c in cluster)
    strongest_type = sorted(cluster, key=lambda c: SOURCE_TYPE_RANK.get(c.item.source_type, 0), reverse=True)[0].item.source_type

    corroboration_score = (
        max(0, distinct_connectors - 1)
        + max(0, distinct_source_types - 1)
        + max(0, strongest_rank - 1)
    )

    if strongest_type == "official" and distinct_connectors >= 2:
        confidence = "high"
    elif corroboration_score >= 4:
        confidence = "high"
    elif corroboration_score >= 2:
        confidence = "medium"
    else:
        confidence = _confidence_from_source(strongest_type)

    base_level = max(
        SEVERITY_LEVELS[_severity_from_text(" ".join([c.item.title, c.item.text]))]
        for c in cluster
    )
    calibrated_level = base_level

    # Down-calibrate severe claims when corroboration is weak.
    if confidence == "low" and calibrated_level >= SEVERITY_LEVELS["high"] and distinct_connectors < 2:
        calibrated_level -= 1

    # Up-calibrate medium incidents with strong corroboration from diverse sources.
    if confidence == "high" and calibrated_level == SEVERITY_LEVELS["medium"] and distinct_connectors >= 3:
        calibrated_level = SEVERITY_LEVELS["high"]

    return SEVERITY_BY_LEVEL[calibrated_level], confidence


def detect_changes(
    items: List[RawSourceItem],
    previous_hashes: List[str],
    countries: List[str],
    disaster_types: List[str],
    include_unchanged: bool = True,
) -> DedupeResult:
    prior = set(previous_hashes)
    deduped: Dict[str, ProcessedEvent] = {}
    candidates: List[CandidateItem] = []

    for item in items:
        combined_text = " ".join([item.title, item.text, " ".join(item.country_candidates)])
        country = next((c for c in countries if matches_country(combined_text, [c])), countries[0])
        disaster_type = infer_disaster_type(combined_text, disaster_types)
        if not disaster_type:
            continue
        candidates.append(CandidateItem(item=item, country=country, disaster_type=disaster_type))

    clusters = _cluster_candidates(candidates)
    current_hashes: List[str] = []

    for cluster in clusters:
        primary = _pick_primary(cluster)
        event_id = _event_hash(
            primary.item,
            country=primary.country,
            disaster_type=primary.disaster_type,
            representative_title=primary.item.title,
        )
        current_hashes.append(event_id)

        if event_id in deduped:
            continue

        if event_id in prior:
            status = "unchanged"
        else:
            status = _find_similar_status(primary.item.title, deduped)

        severity, confidence = _calibrate_severity_and_confidence(cluster)
        corroboration_sources = len(cluster)
        corroboration_connectors = len({c.item.connector for c in cluster})
        corroboration_source_types = len({c.item.source_type for c in cluster})
        summary_seed = primary.item.text if primary.item.text else primary.item.title
        summary = summary_seed[:260].strip()
        summary = f"{summary} [corroboration_sources={corroboration_sources}]"

        event = ProcessedEvent(
            event_id=event_id,
            status=status,
            connector=primary.item.connector,
            source_type=primary.item.source_type,
            url=primary.item.url,
            canonical_url=primary.item.canonical_url,
            title=primary.item.title,
            country=primary.country,
            disaster_type=primary.disaster_type,
            published_at=primary.item.published_at,
            severity=severity,
            confidence=confidence,
            summary=summary,
            corroboration_sources=corroboration_sources,
            corroboration_connectors=corroboration_connectors,
            corroboration_source_types=corroboration_source_types,
        )
        deduped[event_id] = event

    produced = list(deduped.values())
    if not include_unchanged:
        produced = [e for e in produced if e.status != "unchanged"]
    return DedupeResult(events=produced, current_hashes=sorted(set(current_hashes)))

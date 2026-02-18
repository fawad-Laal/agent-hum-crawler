"""Cycle orchestration for collection, dedupe, and persistence."""

from __future__ import annotations

from dataclasses import dataclass

from .config import RuntimeConfig
from .connectors import (
    GovernmentConnector,
    NGOConnector,
    ReliefWebConnector,
    UNConnector,
    build_local_news_connector,
)
from .database import persist_cycle
from .dedupe import detect_changes
from .llm_enrichment import enrich_events_with_llm
from .models import ProcessedEvent, RawSourceItem
from .settings import get_reliefweb_appname, is_llm_enrichment_enabled, is_reliefweb_enabled
from .source_registry import load_registry
from .state import RuntimeState, load_state, save_state


@dataclass
class CycleResult:
    cycle_id: int
    summary: str
    connector_count: int
    raw_item_count: int
    event_count: int
    events: list[ProcessedEvent]
    connector_metrics: list[dict]
    llm_enrichment: dict


def run_cycle_once(
    config: RuntimeConfig,
    limit: int,
    include_content: bool,
) -> CycleResult:
    all_items: list[RawSourceItem] = []
    connector_count = 0
    connector_metrics: list[dict] = []
    registry = load_registry(config.countries)
    local_news_urls = [f.url for f in registry.local_news]
    local_news_urls.extend(config.priority_sources)
    local_news_urls = sorted(set(local_news_urls))

    if is_reliefweb_enabled():
        try:
            reliefweb = ReliefWebConnector(appname=get_reliefweb_appname())
            rw = reliefweb.fetch(config=config, limit=limit, include_content=include_content)
            all_items.extend(rw.items)
            connector_count += 1
            connector_metrics.append(rw.connector_metrics)
        except Exception as exc:
            print(f"Warning: ReliefWeb connector skipped ({exc})")
            connector_metrics.append(
                {
                    "connector": "reliefweb",
                    "attempted_sources": 1,
                    "healthy_sources": 0,
                    "failed_sources": 1,
                    "fetched_count": 0,
                    "matched_count": 0,
                    "errors": [str(exc)],
                    "source_results": [
                        {
                            "source_name": "ReliefWeb Reports API",
                            "source_url": "https://api.reliefweb.int/v1/reports",
                            "status": "failed",
                            "error": str(exc),
                            "fetched_count": 0,
                            "matched_count": 0,
                        }
                    ],
                }
            )
    else:
        print("Info: ReliefWeb disabled (RELIEFWEB_ENABLED=false), running fallback connectors only.")

    for connector in [
        GovernmentConnector(feeds=registry.government),
        UNConnector(feeds=registry.un),
        NGOConnector(feeds=registry.ngo),
        build_local_news_connector(local_news_urls),
    ]:
        if not connector.feeds:
            continue
        try:
            result = connector.fetch(config=config, limit=limit, include_content=include_content)
            all_items.extend(result.items)
            connector_count += 1
            connector_metrics.append(result.connector_metrics)
        except Exception as exc:
            print(f"Warning: connector {connector.connector_name} skipped ({exc})")
            connector_metrics.append(
                {
                    "connector": connector.connector_name,
                    "attempted_sources": len(connector.feeds),
                    "healthy_sources": 0,
                    "failed_sources": len(connector.feeds),
                    "fetched_count": 0,
                    "matched_count": 0,
                    "errors": [str(exc)],
                    "source_results": [
                        {
                            "source_name": feed.name,
                            "source_url": feed.url,
                            "status": "failed",
                            "error": str(exc),
                            "fetched_count": 0,
                            "matched_count": 0,
                        }
                        for feed in connector.feeds
                    ],
                }
            )

    prior_state = load_state()
    if not isinstance(prior_state, RuntimeState):
        prior_state = RuntimeState()

    dedupe = detect_changes(
        items=all_items,
        previous_hashes=prior_state.last_cycle_hashes,
        countries=config.countries,
        disaster_types=config.disaster_types,
        include_unchanged=False,
    )

    events = dedupe.events
    llm_stats = {
        "enabled": False,
        "attempted_count": 0,
        "enriched_count": 0,
        "fallback_count": len(events),
        "provider_error_count": 0,
        "validation_fail_count": 0,
        "insufficient_text_count": len(events),
    }
    if is_llm_enrichment_enabled():
        events, llm_stats = enrich_events_with_llm(events, all_items)

    summary = (
        f"Cycle complete: items={len(all_items)}, events={len(dedupe.events)}, "
        f"new={sum(1 for e in dedupe.events if e.status == 'new')}, "
        f"updated={sum(1 for e in dedupe.events if e.status == 'updated')}, "
        f"llm_enrichment_used={str(llm_stats['enabled']).lower()}, "
        f"llm_enriched={llm_stats['enriched_count']}, llm_fallback={llm_stats['fallback_count']}"
    )

    cycle_id = persist_cycle(
        raw_items=all_items,
        events=events,
        connector_count=connector_count,
        summary=summary,
        connector_metrics=connector_metrics,
        llm_stats=llm_stats,
    )

    prior_state.touch()
    prior_state.last_summary = summary
    prior_state.last_cycle_hashes = dedupe.current_hashes
    save_state(prior_state)

    return CycleResult(
        cycle_id=cycle_id,
        summary=summary,
        connector_count=connector_count,
        raw_item_count=len(all_items),
        event_count=len(events),
        events=events,
        connector_metrics=connector_metrics,
        llm_enrichment=llm_stats,
    )

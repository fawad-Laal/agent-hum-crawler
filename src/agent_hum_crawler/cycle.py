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
from .models import ProcessedEvent, RawSourceItem
from .settings import get_reliefweb_appname, is_reliefweb_enabled
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


def run_cycle_once(
    config: RuntimeConfig,
    limit: int,
    include_content: bool,
) -> CycleResult:
    all_items: list[RawSourceItem] = []
    connector_count = 0
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
        except Exception as exc:
            print(f"Warning: ReliefWeb connector skipped ({exc})")
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
        except Exception as exc:
            print(f"Warning: connector {connector.connector_name} skipped ({exc})")

    prior_state = load_state()
    if not isinstance(prior_state, RuntimeState):
        prior_state = RuntimeState()

    dedupe = detect_changes(
        items=all_items,
        previous_hashes=prior_state.last_cycle_hashes,
        countries=config.countries,
        disaster_types=config.disaster_types,
    )

    summary = (
        f"Cycle complete: items={len(all_items)}, events={len(dedupe.events)}, "
        f"new={sum(1 for e in dedupe.events if e.status == 'new')}, "
        f"updated={sum(1 for e in dedupe.events if e.status == 'updated')}"
    )

    cycle_id = persist_cycle(
        raw_items=all_items,
        events=dedupe.events,
        connector_count=connector_count,
        summary=summary,
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
        event_count=len(dedupe.events),
        events=dedupe.events,
    )

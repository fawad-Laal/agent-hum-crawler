"""Country source registry and allowlist resolution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .connectors.feed_base import FeedSource


@dataclass
class SourceRegistry:
    government: list[FeedSource] = field(default_factory=list)
    un: list[FeedSource] = field(default_factory=list)
    ngo: list[FeedSource] = field(default_factory=list)
    local_news: list[FeedSource] = field(default_factory=list)


def _default_registry() -> SourceRegistry:
    return SourceRegistry(
        government=[
            FeedSource("USGS Earthquakes", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.atom"),
            FeedSource("GDACS", "https://www.gdacs.org/xml/rss.xml"),
        ],
        un=[
            FeedSource("UN News Climate", "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml"),
            FeedSource(
                "UN News Humanitarian",
                "https://news.un.org/feed/subscribe/en/news/topic/humanitarian-aid/feed/rss.xml",
            ),
        ],
        ngo=[FeedSource("IFRC News", "https://www.ifrc.org/rss.xml")],
        local_news=[],
    )


def default_registry_path() -> Path:
    return Path.cwd() / "config" / "country_sources.json"


def _parse_feeds(block: list[dict[str, Any]] | None) -> list[FeedSource]:
    feeds: list[FeedSource] = []
    for item in block or []:
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if name and url:
            feeds.append(FeedSource(name=name, url=url))
    return feeds


def _merge_unique(base: list[FeedSource], extra: list[FeedSource]) -> list[FeedSource]:
    seen = {(f.name.casefold(), f.url.casefold()) for f in base}
    merged = list(base)
    for feed in extra:
        key = (feed.name.casefold(), feed.url.casefold())
        if key not in seen:
            merged.append(feed)
            seen.add(key)
    return merged


def load_registry(countries: list[str], path: Path | None = None) -> SourceRegistry:
    registry_path = path or default_registry_path()
    result = _default_registry()
    if not registry_path.exists():
        return result

    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    global_block = payload.get("global", {})
    country_block = payload.get("countries", {})

    result.government = _merge_unique(result.government, _parse_feeds(global_block.get("government")))
    result.un = _merge_unique(result.un, _parse_feeds(global_block.get("un")))
    result.ngo = _merge_unique(result.ngo, _parse_feeds(global_block.get("ngo")))
    result.local_news = _merge_unique(result.local_news, _parse_feeds(global_block.get("local_news")))

    for country in countries:
        country_cfg = country_block.get(country, {})
        result.government = _merge_unique(result.government, _parse_feeds(country_cfg.get("government")))
        result.un = _merge_unique(result.un, _parse_feeds(country_cfg.get("un")))
        result.ngo = _merge_unique(result.ngo, _parse_feeds(country_cfg.get("ngo")))
        result.local_news = _merge_unique(result.local_news, _parse_feeds(country_cfg.get("local_news")))

    return result

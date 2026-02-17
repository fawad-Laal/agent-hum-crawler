"""UN source connector (RSS/Atom based)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .feed_base import FeedConnector, FeedSource


@dataclass
class UNConnector(FeedConnector):
    connector_name: str = "un_humanitarian_feeds"
    source_type: str = "humanitarian"
    feeds: list[FeedSource] = field(
        default_factory=lambda: [
            FeedSource("UN News Climate", "https://news.un.org/feed/subscribe/en/news/topic/climate-change/feed/rss.xml"),
            FeedSource("UN News Humanitarian", "https://news.un.org/feed/subscribe/en/news/topic/humanitarian-aid/feed/rss.xml"),
        ]
    )

"""Local news connector (RSS/Atom based)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .feed_base import FeedConnector, FeedSource


@dataclass
class LocalNewsConnector(FeedConnector):
    connector_name: str = "local_news_feeds"
    source_type: str = "news"
    feeds: list[FeedSource] = field(default_factory=list)


def build_local_news_connector(feed_urls: list[str]) -> LocalNewsConnector:
    feeds = [FeedSource(name=f"LocalFeed-{idx+1}", url=url) for idx, url in enumerate(feed_urls)]
    return LocalNewsConnector(feeds=feeds)

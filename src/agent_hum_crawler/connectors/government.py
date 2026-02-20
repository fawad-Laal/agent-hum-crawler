"""Government source connector (RSS/Atom based)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .feed_base import FeedConnector, FeedSource


@dataclass
class GovernmentConnector(FeedConnector):
    connector_name: str = "government_feeds"
    source_type: str = "official"
    feeds: list[FeedSource] = field(
        default_factory=lambda: [
            FeedSource("USGS Earthquakes", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.atom"),
            FeedSource("GDACS All 7d", "https://www.gdacs.org/xml/rss_7d.xml"),
            FeedSource("GDACS Floods 7d", "https://www.gdacs.org/xml/rss_fl_7d.xml"),
            FeedSource("GDACS Cyclones 7d", "https://www.gdacs.org/xml/rss_tc_7d.xml"),
        ]
    )

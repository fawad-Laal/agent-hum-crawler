"""NGO source connector (RSS/Atom based)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .feed_base import FeedConnector, FeedSource


@dataclass
class NGOConnector(FeedConnector):
    connector_name: str = "ngo_feeds"
    source_type: str = "humanitarian"
    feeds: list[FeedSource] = field(
        default_factory=lambda: [
            FeedSource("IFRC News", "https://www.ifrc.org/rss.xml"),
            FeedSource("MSF Latest", "https://www.msf.org/rss.xml"),
        ]
    )

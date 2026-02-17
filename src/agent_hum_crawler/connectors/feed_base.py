"""Generic RSS/Atom connector base implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import feedparser
import httpx
import trafilatura
from bs4 import BeautifulSoup

from ..config import RuntimeConfig
from ..models import ContentSource, FetchResult, RawSourceItem
from ..taxonomy import matches_config


@dataclass
class FeedSource:
    name: str
    url: str


@dataclass
class FeedConnector:
    connector_name: str
    source_type: str
    feeds: List[FeedSource]
    timeout_seconds: int = 20

    def fetch(self, config: RuntimeConfig, limit: int = 20, include_content: bool = True) -> FetchResult:
        if not self.feeds:
            return FetchResult(items=[], total_fetched=0, total_matched=0)

        matched: List[RawSourceItem] = []
        total_fetched = 0

        with httpx.Client(timeout=self.timeout_seconds) as client:
            for feed in self.feeds:
                parsed = feedparser.parse(feed.url)
                entries = parsed.entries[: max(1, limit)]
                total_fetched += len(entries)

                for entry in entries:
                    item = self._entry_to_item(entry, feed.name, include_content=include_content, client=client)
                    if not item:
                        continue
                    if matches_config(
                        title=item.title,
                        text=item.text,
                        country_candidates=item.country_candidates,
                        countries=config.countries,
                        disaster_types=config.disaster_types,
                    ):
                        matched.append(item)

        return FetchResult(items=matched, total_fetched=total_fetched, total_matched=len(matched))

    def _entry_to_item(
        self,
        entry: object,
        source_name: str,
        include_content: bool,
        client: httpx.Client,
    ) -> RawSourceItem | None:
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        if not title or not link:
            return None

        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        published = getattr(entry, "published", None) or getattr(entry, "updated", None)

        text = self._extract_text(summary)
        content_sources = [ContentSource(type="web_page", url=link)]

        if include_content:
            page_text = self._fetch_page_text(client, link)
            if page_text:
                text = (text + "\n\n" + page_text).strip()

        return RawSourceItem(
            connector=self.connector_name,
            source_type=self.source_type,
            url=link,
            title=f"[{source_name}] {title}",
            published_at=published,
            country_candidates=[],
            text=text,
            language=None,
            content_mode="content-level" if include_content else "link-level",
            content_sources=content_sources,
        )

    def _extract_text(self, html_or_text: str) -> str:
        if not html_or_text:
            return ""
        extracted = trafilatura.extract(html_or_text)
        if extracted:
            return extracted.strip()
        return BeautifulSoup(html_or_text, "html.parser").get_text(" ", strip=True)

    def _fetch_page_text(self, client: httpx.Client, url: str) -> str:
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return ""
        extracted = trafilatura.extract(response.text)
        if extracted:
            return extracted.strip()
        return BeautifulSoup(response.text, "html.parser").get_text(" ", strip=True)

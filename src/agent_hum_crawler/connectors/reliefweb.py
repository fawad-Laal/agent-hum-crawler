"""ReliefWeb connector with link-level and optional content-level extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import httpx
import trafilatura
from bs4 import BeautifulSoup

from ..config import RuntimeConfig
from ..models import ContentSource, FetchResult, RawSourceItem
from ..taxonomy import matches_config


@dataclass
class ReliefWebConnector:
    appname: str
    timeout_seconds: int = 30
    base_url: str = "https://api.reliefweb.int/v1/reports"

    def _build_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds)

    def fetch(
        self,
        config: RuntimeConfig,
        limit: int = 20,
        include_content: bool = True,
    ) -> FetchResult:
        with self._build_client() as client:
            response = client.get(
                self.base_url,
                params={
                    "appname": self.appname,
                    "limit": max(1, min(limit, 200)),
                    "profile": "full",
                    "sort[]": "date:desc",
                },
            )
            response.raise_for_status()
            payload = response.json()

            data = payload.get("data", [])
            raw_items: List[RawSourceItem] = []
            for entry in data:
                item = self._map_entry_to_item(entry, include_content=include_content, client=client)
                if item and self._matches_config(item, config):
                    raw_items.append(item)

            return FetchResult(
                items=raw_items,
                total_fetched=len(data),
                total_matched=len(raw_items),
            )

    def _map_entry_to_item(
        self,
        entry: dict,
        include_content: bool,
        client: httpx.Client,
    ) -> RawSourceItem | None:
        fields = entry.get("fields", {})
        title = fields.get("title") or ""
        if not title:
            return None

        url = fields.get("url_alias") or entry.get("href")
        if not url:
            return None

        body_html = fields.get("body-html") or fields.get("body") or ""
        text = self._extract_text(body_html)

        countries = [c.get("name", "").strip() for c in fields.get("country", []) if c.get("name")]

        language_list = fields.get("language", [])
        language = None
        if language_list:
            language = language_list[0].get("code") or language_list[0].get("name")

        published_at = self._extract_date(fields)

        content_sources = [ContentSource(type="web_page", url=url)]

        if include_content:
            fetched_text = self._fetch_page_text(client, url)
            if fetched_text:
                text = (text + "\n\n" + fetched_text).strip()

            for f in fields.get("file", []) or []:
                file_url = f.get("url")
                if file_url and str(file_url).lower().endswith(".pdf"):
                    content_sources.append(ContentSource(type="document_pdf", url=file_url))
                elif file_url:
                    content_sources.append(ContentSource(type="document_html", url=file_url))

        return RawSourceItem(
            connector="reliefweb",
            source_type="humanitarian",
            url=url,
            title=title,
            published_at=published_at,
            country_candidates=[c for c in countries if c],
            text=text,
            language=language,
            content_mode="content-level" if include_content else "link-level",
            content_sources=content_sources,
        )

    def _extract_date(self, fields: dict) -> str | None:
        date_block = fields.get("date") or {}
        if isinstance(date_block, dict):
            return date_block.get("original") or date_block.get("created") or date_block.get("changed")
        return None

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

    def _matches_config(self, item: RawSourceItem, config: RuntimeConfig) -> bool:
        return matches_config(
            title=item.title,
            text=item.text,
            country_candidates=item.country_candidates,
            countries=config.countries,
            disaster_types=config.disaster_types,
        )

"""ReliefWeb connector with link-level and optional content-level extraction."""

from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from typing import List

import httpx
import trafilatura
from bs4 import BeautifulSoup

from ..config import RuntimeConfig
from ..models import ContentSource, FetchResult, RawSourceItem
from ..pdf_extract import extract_pdf_document, extract_pdf_text
from ..source_freshness import evaluate_freshness, load_state, save_state, should_demote, update_source_state
from ..taxonomy import match_with_reason
from ..url_canonical import canonicalize_url

logger = logging.getLogger(__name__)

# ReliefWeb API caps results at 1 000 per query (10 pages × 100).
_MAX_PAGE_SIZE = 100
_MAX_PAGES = 10


@dataclass
class ReliefWebConnector:
    appname: str
    timeout_seconds: int = 30
    base_url: str = "https://api.reliefweb.int/v2/reports"

    def __post_init__(self) -> None:
        if not self.appname or self.appname.strip() in ("", "test", "example"):
            raise ValueError(
                "ReliefWeb requires a registered appname. "
                "See https://apidoc.reliefweb.int/#authentication"
            )

    def _build_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout_seconds)

    def fetch(
        self,
        config: RuntimeConfig,
        limit: int = 20,
        include_content: bool = True,
    ) -> FetchResult:
        freshness_state = load_state()
        if should_demote(freshness_state, self.base_url):
            row = update_source_state(
                freshness_state,
                source_url=self.base_url,
                latest_published_at=str((freshness_state.get("sources", {}).get(self.base_url, {}) or {}).get("latest_published_at", "")) or None,
                freshness_status="stale",
                status="demoted_stale",
            )
            save_state(freshness_state)
            return FetchResult(
                items=[],
                total_fetched=0,
                total_matched=0,
                connector_metrics={
                    "connector": "reliefweb",
                    "attempted_sources": 1,
                    "healthy_sources": 0,
                    "failed_sources": 0,
                    "fetched_count": 0,
                    "matched_count": 0,
                    "errors": [],
                    "warnings": ["ReliefWeb auto-demoted due to repeated stale source checks"],
                    "source_results": [
                        {
                            "source_name": "ReliefWeb Reports API",
                            "source_url": self.base_url,
                            "status": "demoted_stale",
                            "error": "auto-demoted due to repeated stale source checks",
                            "fetched_count": 0,
                            "matched_count": 0,
                            "latest_published_at": row.get("latest_published_at"),
                            "freshness_status": "stale",
                            "stale_streak": int(row.get("stale_streak", 0) or 0),
                            "stale_action": row.get("stale_action"),
                            "match_reasons": {
                                "matched": 0,
                                "country_miss": 0,
                                "hazard_miss": 0,
                                "age_filtered": 0,
                            },
                        }
                    ],
                },
            )

        with self._build_client() as client:
            # ── Offset-based pagination ─────────────────────────────
            page_size = min(limit, _MAX_PAGE_SIZE)
            all_data: list[dict] = []
            offset = 0
            pages = 0
            while pages < _MAX_PAGES and len(all_data) < limit:
                query_body = self._build_query_payload(
                    config=config, limit=page_size,
                )
                query_body["offset"] = offset
                response = client.post(
                    self.base_url,
                    params={"appname": self.appname},
                    json=query_body,
                )
                response.raise_for_status()
                payload = response.json()
                page_data = payload.get("data", [])
                if not page_data:
                    break
                all_data.extend(page_data)
                pages += 1
                offset += len(page_data)
                # If the API returned fewer items than page_size, we've
                # exhausted results — no need for another request.
                if len(page_data) < page_size:
                    break

            # Trim to requested limit
            data = all_data[:limit]

            raw_items: List[RawSourceItem] = []
            source_result = {
                "source_name": "ReliefWeb Reports API",
                "source_url": self.base_url,
                "status": "ok",
                "error": "",
                "fetched_count": len(data),
                "matched_count": 0,
                "latest_published_at": self._extract_date(data[0].get("fields", {})) if data else None,
                "match_reasons": {
                    "matched": 0,
                    "country_miss": 0,
                    "hazard_miss": 0,
                    "age_filtered": 0,
                },
            }
            freshness = evaluate_freshness(source_result.get("latest_published_at"), config.max_item_age_days)
            row = update_source_state(
                freshness_state,
                source_url=self.base_url,
                latest_published_at=source_result.get("latest_published_at"),
                freshness_status=freshness.status,
                status="ok",
            )
            source_result["freshness_status"] = freshness.status
            source_result["stale_streak"] = int(row.get("stale_streak", 0) or 0)
            source_result["stale_action"] = row.get("stale_action")
            source_result["latest_age_days"] = freshness.age_days
            for entry in data:
                item = self._map_entry_to_item(entry, include_content=include_content, client=client)
                if not item:
                    continue
                is_match, reason = self._matches_config(item, config)
                source_result["match_reasons"][reason] = int(source_result["match_reasons"].get(reason, 0) or 0) + 1
                if is_match:
                    raw_items.append(item)
                    source_result["matched_count"] += 1
            save_state(freshness_state)

            if pages > 1:
                logger.info("ReliefWeb: fetched %d items across %d pages", len(data), pages)

            return FetchResult(
                items=raw_items,
                total_fetched=len(data),
                total_matched=len(raw_items),
                connector_metrics={
                    "connector": "reliefweb",
                    "attempted_sources": 1,
                    "healthy_sources": 1,
                    "failed_sources": 0,
                    "fetched_count": len(data),
                    "matched_count": len(raw_items),
                    "errors": [],
                    "warnings": (
                        [f"ReliefWeb stale for {source_result['stale_streak']} checks"]
                        if source_result.get("stale_action") == "warn"
                        else []
                    ),
                    "source_results": [source_result],
                },
            )

    # ── Streaming ingestion (Phase 2 — generator pattern) ─────────

    def fetch_stream(
        self,
        config: RuntimeConfig,
        limit: int = 20,
        include_content: bool = True,
    ) -> Generator[RawSourceItem, None, None]:
        """Yield ``RawSourceItem`` objects one-at-a-time as pages arrive.

        Memory-efficient alternative to ``fetch()`` for large result sets.
        Items are yielded as soon as they pass config matching, without
        waiting for all pages to complete.
        """
        with self._build_client() as client:
            page_size = min(limit, _MAX_PAGE_SIZE)
            offset = 0
            pages = 0
            yielded = 0

            while pages < _MAX_PAGES and yielded < limit:
                query_body = self._build_query_payload(
                    config=config, limit=page_size,
                )
                query_body["offset"] = offset
                try:
                    response = client.post(
                        self.base_url,
                        params={"appname": self.appname},
                        json=query_body,
                    )
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("ReliefWeb stream page %d failed: %s", pages, exc)
                    break

                payload = response.json()
                page_data = payload.get("data", [])
                if not page_data:
                    break

                for entry in page_data:
                    if yielded >= limit:
                        break
                    item = self._map_entry_to_item(
                        entry, include_content=include_content, client=client,
                    )
                    if not item:
                        continue
                    is_match, _reason = self._matches_config(item, config)
                    if is_match:
                        yield item
                        yielded += 1

                pages += 1
                offset += len(page_data)
                if len(page_data) < page_size:
                    break

            if pages > 1:
                logger.info(
                    "ReliefWeb stream: yielded %d items across %d pages",
                    yielded, pages,
                )

    def _build_query_payload(self, *, config: RuntimeConfig, limit: int) -> dict:
        keywords: list[str] = []
        keywords.extend([c for c in config.countries if c])

        # Import taxonomy keywords so compound disaster names expand
        # to meaningful search terms rather than literal strings.
        from ..taxonomy import DISASTER_KEYWORDS

        for d in config.disaster_types:
            expanded = DISASTER_KEYWORDS.get(d)
            if expanded:
                # Use first 5 keywords to keep query manageable
                keywords.extend(expanded[:5])
            else:
                keywords.append(d)

        seen: set[str] = set()
        query_terms: list[str] = []
        for k in keywords:
            token = str(k).strip()
            if not token:
                continue
            lk = token.lower()
            if lk in seen:
                continue
            seen.add(lk)
            query_terms.append(token)

        body: dict = {
            "limit": max(1, min(int(limit), _MAX_PAGE_SIZE)),
            "preset": "latest",
            "profile": "full",
            "sort": ["date:desc"],
            "fields": {
                "include": [
                    "title",
                    "url_alias",
                    "date",
                    "country",
                    "language",
                    "body",
                    "body-html",
                    "file",
                    # Extra metadata for enrichment
                    "disaster.name",
                    "format.name",
                    "source.name",
                    "theme.name",
                ]
            },
        }
        if query_terms:
            body["query"] = {"value": " AND ".join(query_terms[:12])}

        # Server-side date filter — avoids pulling ancient reports
        max_age = getattr(config, "max_item_age_days", 0) or 0
        if max_age > 0:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=max_age)
            ).strftime("%Y-%m-%dT00:00:00+00:00")
            body["filter"] = {
                "field": "date.original",
                "value": {"from": cutoff},
            }

        return body

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

        # Extract metadata from enriched fields
        source_names = [
            s.get("name", "").strip()
            for s in fields.get("source", [])
            if s.get("name")
        ]
        source_label = ", ".join(source_names[:3]) if source_names else None

        content_sources = [ContentSource(type="web_page", url=url)]

        if include_content:
            fetched_text = self._fetch_page_text(client, url)
            if fetched_text:
                text = (text + "\n\n" + fetched_text).strip()

            for f in fields.get("file", []) or []:
                file_url = f.get("url")
                if file_url and str(file_url).lower().endswith(".pdf"):
                    content_sources.append(ContentSource(type="document_pdf", url=file_url))
                    # Extract text + tables from PDF
                    pdf_doc = extract_pdf_document(str(file_url), client=client)
                    if pdf_doc.full_text:
                        text = (text + "\n\n" + pdf_doc.full_text).strip()
                elif file_url:
                    content_sources.append(ContentSource(type="document_html", url=file_url))

        return RawSourceItem(
            connector="reliefweb",
            source_type="humanitarian",
            url=url,
            canonical_url=canonicalize_url(str(url), client=client),
            title=title,
            published_at=published_at,
            country_candidates=[c for c in countries if c],
            text=text,
            language=language,
            source_label=source_label,
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

    def _matches_config(self, item: RawSourceItem, config: RuntimeConfig) -> tuple[bool, str]:
        return match_with_reason(
            title=item.title,
            text=item.text,
            country_candidates=item.country_candidates,
            countries=config.countries,
            disaster_types=config.disaster_types,
            published_at=item.published_at,
            max_age_days=config.max_item_age_days,
        )

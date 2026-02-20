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
from ..source_freshness import (
    evaluate_freshness,
    load_state,
    save_state,
    should_demote,
    update_source_state,
)
from ..taxonomy import match_with_reason
from ..url_canonical import canonicalize_url


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
            return FetchResult(
                items=[],
                total_fetched=0,
                total_matched=0,
                connector_metrics={
                    "connector": self.connector_name,
                    "attempted_sources": 0,
                    "healthy_sources": 0,
                    "failed_sources": 0,
                    "fetched_count": 0,
                    "matched_count": 0,
                    "errors": [],
                    "source_results": [],
                },
            )

        matched: List[RawSourceItem] = []
        total_fetched = 0
        source_results: list[dict] = []
        errors: list[str] = []
        healthy_sources = 0
        failed_sources = 0
        freshness_state = load_state()
        warnings: list[str] = []

        with httpx.Client(timeout=self.timeout_seconds) as client:
            for feed in self.feeds:
                if should_demote(freshness_state, feed.url):
                    row = update_source_state(
                        freshness_state,
                        source_url=feed.url,
                        latest_published_at=(
                            str((freshness_state.get("sources", {}).get(feed.url, {}) or {}).get("latest_published_at", ""))
                            or None
                        ),
                        freshness_status="stale",
                        status="demoted_stale",
                    )
                    source_results.append(
                        {
                            "source_name": feed.name,
                            "source_url": feed.url,
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
                    )
                    warnings.append(f"{feed.name}: auto-demoted due to stale streak")
                    continue
                try:
                    parsed = feedparser.parse(feed.url)
                except Exception as exc:
                    failed_sources += 1
                    error = f"{feed.name}: {exc}"
                    errors.append(error)
                    source_results.append(
                        {
                            "source_name": feed.name,
                            "source_url": feed.url,
                            "status": "failed",
                            "error": str(exc),
                            "fetched_count": 0,
                            "matched_count": 0,
                            "match_reasons": {
                                "matched": 0,
                                "country_miss": 0,
                                "hazard_miss": 0,
                                "age_filtered": 0,
                            },
                        }
                    )
                    continue

                if getattr(parsed, "bozo", False):
                    bozo_exc = getattr(parsed, "bozo_exception", "feed parse error")
                    entries, recovery_error = self._recover_bozo_entries(client, feed.url, limit)
                    if entries:
                        healthy_sources += 1
                        source_results.append(
                            {
                                "source_name": feed.name,
                                "source_url": feed.url,
                                "status": "recovered",
                                "error": str(bozo_exc),
                                "fetched_count": len(entries),
                                "matched_count": 0,
                                "latest_published_at": self._entry_published(entries[0]) if entries else None,
                                "match_reasons": {
                                    "matched": 0,
                                    "country_miss": 0,
                                    "hazard_miss": 0,
                                    "age_filtered": 0,
                                },
                            }
                        )
                    else:
                        failed_sources += 1
                        error_text = str(recovery_error or bozo_exc)
                        errors.append(f"{feed.name}: {error_text}")
                        source_results.append(
                            {
                                "source_name": feed.name,
                                "source_url": feed.url,
                                "status": "failed",
                                "error": error_text,
                                "fetched_count": 0,
                                "matched_count": 0,
                                "match_reasons": {
                                    "matched": 0,
                                    "country_miss": 0,
                                    "hazard_miss": 0,
                                    "age_filtered": 0,
                                },
                            }
                        )
                else:
                    healthy_sources += 1
                    entries = parsed.entries[: max(1, limit)]
                    source_results.append(
                        {
                            "source_name": feed.name,
                            "source_url": feed.url,
                            "status": "ok",
                            "error": "",
                            "fetched_count": len(entries),
                            "matched_count": 0,
                            "latest_published_at": self._entry_published(entries[0]) if entries else None,
                            "match_reasons": {
                                "matched": 0,
                                "country_miss": 0,
                                "hazard_miss": 0,
                                "age_filtered": 0,
                            },
                        }
                    )
                total_fetched += len(entries)
                latest_published_at = source_results[-1].get("latest_published_at")
                freshness = evaluate_freshness(latest_published_at, config.max_item_age_days)
                row = update_source_state(
                    freshness_state,
                    source_url=feed.url,
                    latest_published_at=latest_published_at,
                    freshness_status=freshness.status,
                    status=str(source_results[-1].get("status", "unknown")),
                )
                source_results[-1]["freshness_status"] = freshness.status
                source_results[-1]["stale_streak"] = int(row.get("stale_streak", 0) or 0)
                source_results[-1]["stale_action"] = row.get("stale_action")
                source_results[-1]["latest_age_days"] = freshness.age_days
                if row.get("stale_action") == "warn":
                    warnings.append(f"{feed.name}: stale for {row.get('stale_streak', 0)} checks")

                for entry in entries:
                    item = self._entry_to_item(entry, feed.name, include_content=include_content, client=client)
                    if not item:
                        continue
                    is_match, reason = match_with_reason(
                        title=item.title,
                        text=item.text,
                        country_candidates=item.country_candidates,
                        countries=config.countries,
                        disaster_types=config.disaster_types,
                        published_at=item.published_at,
                        max_age_days=config.max_item_age_days,
                    )
                    if is_match:
                        matched.append(item)
                    if source_results:
                        source_results[-1]["matched_count"] += 1 if is_match else 0
                        reasons = source_results[-1].setdefault("match_reasons", {})
                        reasons[reason] = int(reasons.get(reason, 0) or 0) + 1

        save_state(freshness_state)

        return FetchResult(
            items=matched,
            total_fetched=total_fetched,
            total_matched=len(matched),
            connector_metrics={
                "connector": self.connector_name,
                "attempted_sources": len(self.feeds),
                "healthy_sources": healthy_sources,
                "failed_sources": failed_sources,
                "fetched_count": total_fetched,
                "matched_count": len(matched),
                "errors": errors,
                "warnings": warnings,
                "source_results": source_results,
            },
        )

    def _recover_bozo_entries(
        self,
        client: httpx.Client,
        feed_url: str,
        limit: int,
    ) -> tuple[list, str | None]:
        try:
            response = client.get(feed_url, follow_redirects=True)
            response.raise_for_status()
        except Exception as exc:
            return [], str(exc)

        # Retry parsing from raw bytes first.
        parsed = feedparser.parse(response.content)
        if not getattr(parsed, "bozo", False):
            return parsed.entries[: max(1, limit)], None

        # Last resort: decode leniently and parse from text.
        sanitized_text = response.content.decode("utf-8", errors="ignore")
        reparsed = feedparser.parse(sanitized_text.encode("utf-8", errors="ignore"))
        if not getattr(reparsed, "bozo", False):
            return reparsed.entries[: max(1, limit)], None

        bozo_exc = getattr(reparsed, "bozo_exception", "feed parse error")
        return [], str(bozo_exc)

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
        canonical_hint = self._extract_non_google_link(summary) if "news.google." in link.lower() else None
        canonical_url = canonicalize_url(canonical_hint or link, client=client)

        if include_content:
            page_text = self._fetch_page_text(client, link)
            if page_text:
                text = (text + "\n\n" + page_text).strip()

        return RawSourceItem(
            connector=self.connector_name,
            source_type=self.source_type,
            url=link,
            canonical_url=canonical_url,
            title=f"[{source_name}] {title}",
            published_at=published,
            country_candidates=[],
            text=text,
            language=None,
            content_mode="content-level" if include_content else "link-level",
            content_sources=content_sources,
        )

    def _entry_published(self, entry: object) -> str | None:
        return getattr(entry, "published", None) or getattr(entry, "updated", None)

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

    def _extract_non_google_link(self, html_or_text: str) -> str | None:
        if not html_or_text:
            return None
        try:
            soup = BeautifulSoup(html_or_text, "html.parser")
            for a in soup.find_all("a"):
                href = str(a.get("href", "")).strip()
                if not href.startswith(("http://", "https://")):
                    continue
                if "news.google." in href.lower():
                    continue
                return href
        except Exception:
            return None
        return None

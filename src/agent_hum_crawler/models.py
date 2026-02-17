"""Pydantic models for connector outputs and processed events."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ContentSource(BaseModel):
    type: Literal["web_page", "document_pdf", "document_html"]
    url: HttpUrl


class RawSourceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    connector: str
    source_type: Literal["official", "humanitarian", "news", "social"]
    url: HttpUrl
    title: str
    published_at: str | None = None
    country_candidates: List[str] = Field(default_factory=list)
    text: str = ""
    language: str | None = None
    content_mode: Literal["link-level", "content-level"] = "link-level"
    content_sources: List[ContentSource] = Field(default_factory=list)


class FetchResult(BaseModel):
    items: List[RawSourceItem]
    total_fetched: int
    total_matched: int


class ProcessedEvent(BaseModel):
    event_id: str
    status: Literal["new", "updated", "unchanged"]
    connector: str
    source_type: Literal["official", "humanitarian", "news", "social"]
    url: HttpUrl
    title: str
    country: str
    disaster_type: str
    published_at: str | None = None
    severity: Literal["low", "medium", "high", "critical"]
    confidence: Literal["low", "medium", "high"]
    summary: str

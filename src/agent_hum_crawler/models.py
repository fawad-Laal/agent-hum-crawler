"""Pydantic models for connector outputs and processed events."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ContentSource(BaseModel):
    type: Literal["web_page", "document_pdf", "document_html", "document_docx", "document_xlsx"]
    url: HttpUrl


class ExtractionEvent(BaseModel):
    """In-flight telemetry for a single document extraction attempt.

    Populated by connectors during fetch and persisted by ``persist_cycle``
    as an ``ExtractionRecord`` row (Phase 9.3).
    """

    attachment_url: str
    connector: str
    downloaded: bool = False
    status: Literal["ok", "empty", "failed", "skipped"]
    method: str  # "pdfplumber" | "pypdf" | "trafilatura" | "bs4" | "none"
    char_count: int = 0
    duration_ms: int = 0
    error: str = ""


class RawSourceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    connector: str
    source_type: Literal["official", "humanitarian", "news", "social"]
    url: HttpUrl
    canonical_url: HttpUrl | None = None
    title: str
    published_at: str | None = None
    country_candidates: List[str] = Field(default_factory=list)
    text: str = ""
    language: str | None = None
    source_label: str | None = None
    content_mode: Literal["link-level", "content-level"] = "link-level"
    content_sources: List[ContentSource] = Field(default_factory=list)
    extraction_events: List[ExtractionEvent] = Field(default_factory=list)
    # Phase 9.1: original external source URL from ReliefWeb 'origin' field
    origin_url: str | None = None


class FetchResult(BaseModel):
    items: List[RawSourceItem]
    total_fetched: int
    total_matched: int
    connector_metrics: dict = Field(default_factory=dict)


class EventCitation(BaseModel):
    url: HttpUrl
    quote: str
    quote_start: int
    quote_end: int


class ProcessedEvent(BaseModel):
    event_id: str
    status: Literal["new", "updated", "unchanged"]
    connector: str
    source_type: Literal["official", "humanitarian", "news", "social"]
    url: HttpUrl
    canonical_url: HttpUrl | None = None
    title: str
    country: str
    country_iso3: str = ""
    disaster_type: str
    published_at: str | None = None
    severity: Literal["low", "medium", "high", "critical"]
    confidence: Literal["low", "medium", "high"]
    summary: str
    llm_enriched: bool = False
    citations: List[EventCitation] = Field(default_factory=list)
    corroboration_sources: int = 1
    corroboration_connectors: int = 1
    corroboration_source_types: int = 1

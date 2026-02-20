# Situation Analysis — Quality Improvement Analysis

Date: 2026-02-20
Status: **Analysis Complete** — Multi-agent proposal superseded by [Project Clarity](../roadmap/project-clarity-roadmap.md)
Author: Moltis Engineering

---

## Table of Contents

1. [Current Architecture Assessment](#1-current-architecture-assessment)
2. [Root Cause Analysis — SA Output Quality](#2-root-cause-analysis)
3. [Multi-Agent Architecture Proposal](#3-multi-agent-architecture)
4. [ReliefWeb PDF/OCR Strategy](#4-reliefweb-pdfocr-strategy)
5. [Graph RAG Enhancement Plan](#5-graph-rag-enhancement-plan)
6. [Date & Geo Awareness Strategy](#6-date--geo-awareness-strategy)
7. [LLM Prompt Engineering Improvements](#7-llm-prompt-engineering-improvements)
8. [Model Selection Analysis](#8-model-selection-analysis)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Current Architecture Assessment

### 1.1 Pipeline Overview

```
Evidence Sources → Connectors → DB (SQLite) → build_graph_context()
                                                      │
                                              ┌───────┴────────┐
                                              │  Coordinator   │
                                              └───────┬────────┘
                                                      │
                                 ┌────────────────────┼────────────────────┐
                                 │                    │                    │
                           build_ontology()    render_report()    render_sa()
                                 │                                       │
                     graph_ontology.py                        situation_analysis.py
                     (NLP-light extraction)                  (15-section OCHA template)
                                                                         │
                                                              _generate_llm_narratives()
                                                              (single-shot, no schema)
```

### 1.2 Key Modules & Line Counts

| Module | Lines | Purpose |
|--------|-------|---------|
| `situation_analysis.py` | 1,080 | 15-section OCHA-style SA renderer |
| `graph_ontology.py` | 1,174 | Humanitarian ontology graph (7 entity types, Rust-accelerated) |
| `llm_enrichment.py` | 332 | Per-event LLM enrichment with strict JSON schema + citations |
| `coordinator.py` | 439 | Pipeline orchestrator with caching |
| `reliefweb.py` | 290 | ReliefWeb API v2 connector |
| `taxonomy.py` | 121 | Disaster keyword taxonomy (11 types, 26 aliases) |
| `reporting.py` | ~600 | Long-form report renderer |
| `llm_utils.py` | 96 | Shared LLM utility functions |

### 1.3 What Works Today

- **Evidence gathering**: 6 connector types (ReliefWeb, UN, NGO, Government, Local News, Feed Base)
- **Ontology construction**: 7 entity types (GeoArea, HazardNode, ImpactObservation, NeedStatement, RiskStatement, ResponseActivity, SourceClaim)
- **Rust acceleration**: 7 functions wired in (extract_figures, classify_impact_type, classify_need_types, severity_from_text, is_risk_text, detect_response_actor, similarity_ratio) — 23/23 Rust tests passing
- **Per-event LLM enrichment**: Strict JSON schema with citation locking via OpenAI Responses API
- **Template-driven SA**: 15 configurable sections with word limits and sector schemas
- **Deterministic fallback**: Full report renders without LLM when API unavailable
- **150/150 Python tests**, 23/23 Rust tests

### 1.4 Current LLM Model

- **Model**: `gpt-4.1-mini` (env `OPENAI_MODEL`)
- **API**: OpenAI Responses API (`/v1/responses`)
- **Per-event enrichment**: Strict JSON schema enforcement, 30s timeout, 10K text truncation
- **SA narrative generation**: Single-shot, NO JSON schema enforcement, 60s timeout, 30 evidence items with 200-char truncation

---

## 2. Root Cause Analysis

### 2.1 Problem: Garbage Text in Sector Tables

**Observed in Ethiopia SA output:**
> "Countries: Ethiopia, South Sudan Source: UN High Commissioner for Refugees Please refer to the attached Infographic..."

**Root cause — `_render_sector_section()` (situation_analysis.py, line ~745):**

```python
# Current code fills table cells with raw NeedStatement.description
descriptions = [n.description for n in group if n.description]
summary_text = descriptions[0][:120] if descriptions else "See narrative"
for col in table_cols[1:]:
    row.append(summary_text)
    summary_text = "See narrative"
```

**Why this produces garbage:**
1. `NeedStatement.description` stores raw evidence text from `graph_ontology.py`
2. In `build_ontology_from_evidence()`, needs are created with: `description=summary[:200]`
3. The "summary" is the raw `ProcessedEvent.summary` — which is often the source article title or lede paragraph, not a synthesized description
4. The same raw text is then dumped verbatim into multiple table columns
5. The same description fills ALL table columns after the geo column (same text repeated)

### 2.2 Problem: "Unknown Event" Name

**Root cause — `_infer_event_name()` (line ~115):**

```python
def _infer_event_name(evidence):
    for ev in evidence:
        title = ev.get("title", "")
        # Only matches "Cyclone X" / "Typhoon X" patterns
        m = re.search(r"(Cyclone|Typhoon|Hurricane|Storm|Earthquake)\s+\w+", title, re.I)
        if m:
            return m.group(0)
    return "Unknown Event"
```

This regex only catches named storms. For conflict crises (Ethiopia), epidemic outbreaks, or drought events, it returns "Unknown Event" every time.

### 2.3 Problem: Empty Admin Tables

**Root cause — Only 2 country gazetteers exist:**
- Madagascar: 22 provinces, 100+ districts
- Mozambique: 10 provinces, 50+ districts
- **Ethiopia: NONE** — all admin1/admin2 detection returns empty

The `build_auto_admin_hierarchy()` function finds no match for "Ethiopia", so no geographic areas are populated, and all province/district tables show "No province-level data available."

### 2.4 Problem: Raw Evidence in Forecasts

**Root cause — `_render_forecast()` (line ~900):**

```python
risks = ontology.risks_by_horizon(horizon_key)
if risks:
    for risk in risks:
        lines.append(f"- {risk.description}")
```

`RiskStatement.description` stores `summary[:200]` — the raw source summary, not a synthesized forecast. Source text like "[Addis Standard] Addis Abeba -- Every February..." gets dumped as risk outlook.

### 2.5 Problem: No Date Awareness

- `SourceClaim` stores `published_at` but it's never surfaced in SA output
- Evidence digest sent to LLM omits dates entirely:
  ```python
  evidence_digest.append({
      "title": ..., "country": ..., "summary": ...[:200],
      "severity": ..., "connector": ...,
      # NO date field!
  })
  ```
- Temporal reasoning is impossible without dates — the SA can't distinguish a 2-day-old report from a 2-week-old one
- No "as of" dating in any section

### 2.6 Problem: No PDF Content Extraction

**Root cause — `reliefweb.py` (line ~233):**

```python
for f in entry.get("fields", {}).get("file", []):
    file_url = f.get("url", "")
    if file_url:
        content_sources.append(ContentSource(type="document_pdf", url=file_url))
```

PDFs are catalogued as `ContentSource(type="document_pdf")` but **never downloaded or parsed**. Text extraction only processes `body-html` and web pages. ReliefWeb Flash Updates, Situation Reports, and Assessment summaries — the highest-quality structured humanitarian data — are PDF-only and completely missed.

### 2.7 Problem: Figure Deduplication Absent

The same figure from multiple sources gets accumulated:
- Source A: "48,000 people displaced" → `people_affected: 48000`
- Source B: "48,000 displaced in floods" → `people_affected: 48000`
- **National total: 96,000** (doubled)

`_extract_figures()` uses `max()` within a single evidence item but across items they're summed by `aggregate_figures_by_admin1()`.

### 2.8 Problem: Single-Shot SA LLM Call

```python
# SA narrative generation
body = {
    "model": get_openai_model(),
    "input": [...],  # system + user messages only
    # NO "text": {"format": {"type": "json_schema", ...}}
}
```

- No structured output schema — returns free-form text that's parsed as JSON
- 30 evidence items with 200-char truncation (loses critical detail)
- Single call for ALL sections — no specialization
- 60s timeout — insufficient for complex multi-section generation
- No retry logic

### 2.9 Problem: Country Substring Matching Bug

In `taxonomy.py`:
```python
# Case-insensitive substring match
if country_lower in ev_country_lower or ev_country_lower in country_lower:
```
"Niger" matches "Nigeria" and vice versa. This causes cross-contamination of evidence.

---

## 3. Multi-Agent Architecture

### 3.1 Design Principle

Move from a single monolithic LLM call to a **pipeline of specialized agents**, each with a focused task, clear input/output contract, and appropriate model selection.

### 3.2 Proposed Agent Architecture

```
                          ┌─────────────────────┐
                          │  Pipeline Controller │
                          │   (coordinator.py)   │
                          └──────────┬──────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
   ┌────┴─────┐              ┌──────┴──────┐             ┌───────┴───────┐
   │ PHASE 1  │              │   PHASE 2   │             │   PHASE 3     │
   │ Evidence │              │  Ontology   │             │  Synthesis    │
   │ Ingestion│              │  Enrichment │             │  & Rendering  │
   └────┬─────┘              └──────┬──────┘             └───────┬───────┘
        │                           │                            │
   ┌────┴─────┐              ┌──────┴──────┐             ┌───────┴───────┐
   │ OCR Agent│              │ Triage Agent│             │Sector Analysts│
   │ PDF→Text │              │ Classify &  │             │ (6 parallel)  │
   └──────────┘              │ Route       │             └───────┬───────┘
                             └──────┬──────┘                     │
                                    │                    ┌───────┴───────┐
                             ┌──────┴──────┐             │ QA / Synthesis│
                             │ Entity Link │             │    Agent      │
                             │ Agent (NER) │             └───────────────┘
                             └─────────────┘
```

### 3.3 Agent Definitions

#### Agent 1: OCR Extraction Agent
- **Input**: PDF URLs (ReliefWeb Flash Updates, SitReps, Assessment PDFs)
- **Output**: Structured text with metadata (tables, headings, figure boxes)
- **Model**: Not LLM — OCR engine (see Section 4)
- **Trigger**: During evidence ingestion, for each `ContentSource(type="document_pdf")`

#### Agent 2: Evidence Triage Agent
- **Input**: Raw evidence items (titles, summaries, full text, dates, URLs)
- **Output**: Classified evidence with:
  - Date normalization (publication date, event date, data cut-off date)
  - Geographic tagging (country, admin1, admin2 — using LLM NER, not just keyword matching)
  - Relevance scoring (0-1 for the target crisis)
  - Duplicate detection (semantic similarity, not just URL matching)
  - Source credibility tier (primary/secondary/tertiary)
- **Model**: `gpt-4.1-mini` (fast, cheap, good at classification)
- **Schema**: Strict JSON schema per evidence item
- **Batch size**: 10-15 items per call for efficiency
- **Why agent, not rule-based**: Named Entity Recognition for admin areas, temporal reasoning for date extraction, semantic duplicate detection

#### Agent 3: Entity Linking Agent
- **Input**: Triaged evidence + current ontology graph
- **Output**: Updated ontology with:
  - Deduplicated figures (same "48,000 displaced" from multiple sources → single canonical figure with source count)
  - Linked entities (an IDP camp mentioned in 3 sources → single entity with 3 citations)
  - Temporal annotations (figure X was reported on date Y)
  - Confidence scoring based on source count and credibility tier
- **Model**: `gpt-4.1-mini` for entity resolution, rule-based for figure dedup
- **Schema**: Strict JSON — entity ID, canonical value, source references

#### Agent 4: Sector Analyst Agents (6 parallel)
- **Input**: Sector-specific evidence + sector schema from template + ontology needs/impacts for that sector
- **Output**: Per-sector analysis containing:
  - Structured table data (geo area, key figures, severity, priority needs)
  - Narrative paragraph (OCHA prose style, word-limited per template)
  - Key messages (3-5 bullet points per sector)
  - Data gaps identified
- **One agent per sector**: Shelter, WASH, Health, Food Security, Protection, Education
- **Model**: `gpt-4.1` (full model — needs high quality synthesis and OCHA writing style)
- **Schema**: Strict JSON schema per sector
- **Prompt**: Sector-specific system prompt with OCHA style guide, humanitarian standards, and sector-specific terminology

#### Agent 5: Synthesis / QA Agent
- **Input**: All sector outputs + national figures + executive summary draft + admin tables
- **Output**: Final polished SA document with:
  - Coherent executive summary (synthesized, not just concatenated)
  - Cross-references between sections
  - Consistency checks (figures match across sections)
  - "As of" dating on all figures
  - Source attribution (numbered citations)
- **Model**: `gpt-4.1` (full model — needs highest quality for the executive-facing output)
- **Schema**: Strict JSON for each section block

### 3.4 Cross-Cutting Concerns (Apply to ALL Agents)

| Concern | Implementation |
|---------|----------------|
| **Date awareness** | Every evidence item carries `published_at`, `event_date`, `data_cutoff_date`. Agents see and reason about dates. |
| **Geo awareness** | Every evidence item carries `country`, `admin1`, `admin2` (from Agent 2 NER). Agents reason about geographic scope. |
| **Citation locking** | Every synthesized claim must reference source URL + quote span. Claims without citations are rejected. |
| **Fallback** | If any agent fails, the pipeline falls back to deterministic rendering (current behavior, improved). |
| **Schema enforcement** | All LLM calls use OpenAI Responses API `json_schema` format with `strict: true`. |
| **Token budget** | Per-agent token limits to prevent runaway costs. Sector agents: 4K output, Synthesis: 8K output. |
| **Retry policy** | 1 retry with exponential backoff (2s → 4s). On 2nd failure → deterministic fallback. |

### 3.5 Cost Estimate (per SA generation)

| Agent | Model | Input Tokens | Output Tokens | Calls | Est. Cost |
|-------|-------|-------------|---------------|-------|-----------|
| Triage | gpt-4.1-mini | ~3K/batch | ~1K/batch | 5-8 batches | ~$0.02 |
| Entity Link | gpt-4.1-mini | ~4K | ~2K | 1 | ~$0.003 |
| Sector Analysts | gpt-4.1 | ~4K each | ~2K each | 6 parallel | ~$0.36 |
| Synthesis/QA | gpt-4.1 | ~8K | ~4K | 1 | ~$0.12 |
| **Total** | | | | | **~$0.50** |

Compare to current: 1 call × gpt-4.1-mini ≈ $0.01 (but produces garbage).

---

## 4. ReliefWeb PDF/OCR Strategy

### 4.1 The Gap

ReliefWeb hosts the **highest-quality humanitarian data** in PDF format:

- **Flash Updates**: 2-4 page rapid assessments within 24-72 hours of disaster onset
- **Situation Reports**: Weekly 8-20 page structured reports from OCHA offices
- **Assessment Summaries**: Multi-Sector Initial Rapid Assessments (MIRA), Humanitarian Needs Overviews (HNO)
- **Infographics**: Visual situation snapshots with tables and key figures

Currently: PDFs are catalogued (`ContentSource(type="document_pdf")`) but **never downloaded or extracted**. This means we're missing the single most valuable data source for structured humanitarian analysis.

### 4.2 OCR Options Analysis

The user requirement is: **"We dont want to use PDF extractors but OCR that is free or cheap to use as we need quality."** This means we prioritize OCR-based approaches over traditional PDF text extraction (like PyMuPDF or pdfplumber) because many humanitarian PDFs are scanned documents or image-heavy infographics.

#### Option A: Tesseract OCR (Free, Local)

| Attribute | Detail |
|-----------|--------|
| **Cost** | Free (open source, Apache 2.0) |
| **Quality** | Good for clean text; struggles with tables, multi-column layouts, infographics |
| **Speed** | ~2-5 seconds per page |
| **Language** | 100+ languages, trainable |
| **Install** | `pip install pytesseract` + system Tesseract binary |
| **Table detection** | Poor — needs external layout analysis |
| **Output** | Plain text (hOCR for layout-aware) |

**Best for**: Simple text-heavy PDF pages, supplementary extraction.

#### Option B: EasyOCR (Free, Local, Deep Learning)

| Attribute | Detail |
|-----------|--------|
| **Cost** | Free (Apache 2.0) |
| **Quality** | Better than Tesseract for complex layouts; GPU-accelerated |
| **Speed** | ~3-8 seconds per page (GPU), ~15-30s (CPU) |
| **Language** | 80+ languages |
| **Install** | `pip install easyocr` (pulls PyTorch) |
| **Table detection** | Better than Tesseract — deep learning based |
| **Output** | Structured bounding boxes + text |

**Best for**: Mixed text/image PDFs, multi-language documents.

#### Option C: Docling by IBM (Free, Purpose-Built for Documents)

| Attribute | Detail |
|-----------|--------|
| **Cost** | Free (MIT license) |
| **Quality** | Excellent — purpose-built for document understanding with table detection |
| **Speed** | ~5-10 seconds per page |
| **Table detection** | Built-in, high-quality structured table extraction |
| **Install** | `pip install docling` |
| **Output** | Structured document (headings, paragraphs, tables as data) |
| **Key advantage** | Understands document structure — not just OCR, but document understanding |

**Best for**: Structured humanitarian PDFs (Flash Updates, SitReps with standardized layouts).

#### Option D: Azure AI Document Intelligence (Cheap Cloud)

| Attribute | Detail |
|-----------|--------|
| **Cost** | $1.50 per 1,000 pages (prebuilt), $10 per 1,000 pages (custom) |
| **Quality** | Excellent — state of the art for table extraction and structured data |
| **Speed** | ~2-5 seconds per page |
| **Table detection** | Best-in-class — returns structured tables with row/column data |
| **Install** | `pip install azure-ai-documentintelligence` |
| **Output** | Structured JSON (paragraphs, tables, key-value pairs, figures) |
| **Key advantage** | Pre-trained on government/NGO documents, handles complex layouts |

**Best for**: If budget allows, this produces the highest quality output for humanitarian PDFs.

#### Option E: Vision LLM OCR (Uses Existing OpenAI Key)

| Attribute | Detail |
|-----------|--------|
| **Cost** | ~$0.01-0.03 per page (using gpt-4.1-mini with image input) |
| **Quality** | Excellent for understanding context; variable for precise table data |
| **Speed** | ~3-8 seconds per page |
| **Table detection** | Good — understands tables semantically but may miss precise cell boundaries |
| **Install** | Already available (OpenAI API) |
| **Output** | Structured text/JSON (whatever you prompt for) |
| **Key advantage** | Can extract AND summarize in one pass; understands humanitarian context |

**Best for**: When you want extraction + interpretation simultaneously.

### 4.3 Recommended Approach: Tiered Strategy

```
PDF URL from ReliefWeb
        │
        ▼
  ┌──────────────┐
  │ Download PDF  │
  │ (httpx, async)│
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐     Page count ≤ 4?
  │ Page Analysis │────────────────────┐
  │ (pdf2image)   │                    │
  └──────┬───────┘                    │
         │ Yes                         │ No (long SitRep)
         ▼                             ▼
  ┌──────────────┐             ┌──────────────┐
  │  Docling      │            │  Docling for  │
  │  (full doc)   │            │  first 6 pages│
  └──────┬───────┘             │  + exec summ  │
         │                     └──────┬───────┘
         ▼                            ▼
  ┌──────────────┐             ┌──────────────┐
  │ Structured    │            │ Structured    │
  │ Text + Tables │            │ Text + Tables │
  └──────┬───────┘             └──────┬───────┘
         │                            │
         └────────────┬───────────────┘
                      ▼
              ┌──────────────┐
              │ Store as      │
              │  EvidenceItem │
              │ with metadata │
              └──────────────┘
```

**Primary**: Docling (free, MIT, purpose-built for document understanding)
- Handles tables, headings, paragraphs as structured data
- No cloud dependency — runs locally
- Respects document hierarchy

**Fallback**: Tesseract (for images/scans that Docling can't parse)

**Optional upgrade**: Azure AI Document Intelligence (if budget available and quality needs to be higher for specific document types)

### 4.4 Integration Plan

```python
# New module: src/agent_hum_crawler/pdf_extraction.py

class PDFExtractor:
    """Extract structured text from humanitarian PDF documents."""

    async def extract(self, url: str) -> ExtractedDocument:
        """Download and OCR a PDF document."""
        pdf_bytes = await self._download(url)
        pages = self._pdf_to_images(pdf_bytes)

        # Primary: Docling
        result = self._extract_with_docling(pdf_bytes)
        if not result.text.strip():
            # Fallback: Tesseract
            result = self._extract_with_tesseract(pages)

        return ExtractedDocument(
            text=result.text,
            tables=result.tables,      # list[Table] with rows/cols
            headings=result.headings,   # list[str]
            metadata={
                "page_count": len(pages),
                "extraction_method": result.method,
                "extraction_time_ms": result.time_ms,
            },
        )
```

### 4.5 ReliefWeb API Enhancement

Current ReliefWeb connector only fetches 200 results in a single POST. Enhancements needed:

1. **Pagination**: Use `offset` parameter to fetch beyond 200
2. **PDF download**: For each `file` entry, download and extract
3. **Format filtering**: Prioritize Flash Updates and Situation Reports (format codes 10, 12)
4. **Date filtering**: Use `date.created` filter for temporal queries
5. **Full field set**: Request `disaster`, `format`, `theme`, `source` for better metadata

```python
# Enhanced ReliefWeb query
payload = {
    "appname": "moltis-crawler",
    "filter": {
        "operator": "AND",
        "conditions": [
            {"field": "country.name", "value": countries},
            {"field": "date.created", "value": {"from": date_from, "to": date_to}},
            {"field": "format.name", "value": [
                "Flash Update", "Situation Report",
                "Assessment", "Infographic"
            ]},
        ],
    },
    "fields": {
        "include": [
            "title", "url_alias", "date.created", "date.original",
            "country.name", "source.name", "format.name",
            "disaster.name", "disaster.type",
            "theme.name", "language.name",
            "body-html", "file.url", "file.description",
        ],
    },
    "sort": ["date.created:desc"],
    "limit": 200,
    "offset": 0,
}
```

---

## 5. Graph RAG Enhancement Plan

### 5.1 Current Limitations

| # | Limitation | Impact |
|---|-----------|--------|
| 1 | NLP-light extraction (keyword-only) | Misses nuanced needs, misclassifies impact types |
| 2 | No figure deduplication across sources | National figures inflated (48K displaced × 2 sources = 96K) |
| 3 | Single impact type per evidence item | Complex events with multiple impact types get reduced to one |
| 4 | Only 2 country gazetteers (Madagascar, Mozambique) | No admin detection for Ethiopia, Somalia, Sudan, South Sudan, etc. |
| 5 | No temporal layer on graph nodes | Can't distinguish current vs. historical observations |
| 6 | No entity linking across evidence items | Same IDP camp in 3 sources = 3 separate entities |
| 7 | No source credibility weighting | OCHA SitRep weighted same as a social media post |
| 8 | Country substring matching bug | "Niger" matches "Nigeria" |

### 5.2 Enhancement: Temporal Graph Layer

Add temporal annotations to all graph nodes:

```python
@dataclass
class TemporalAnnotation:
    """When was this observation made/valid?"""
    published_at: datetime | None = None    # when source was published
    event_date: datetime | None = None      # when the event occurred
    data_cutoff: datetime | None = None     # "as of" date for figures
    validity_window: str = "current"        # "current", "historical", "projected"

@dataclass
class ImpactObservation:
    # ... existing fields ...
    temporal: TemporalAnnotation = field(default_factory=TemporalAnnotation)

@dataclass
class NeedStatement:
    # ... existing fields ...
    temporal: TemporalAnnotation = field(default_factory=TemporalAnnotation)
```

### 5.3 Enhancement: Figure Deduplication

```python
class FigureDeduplicator:
    """Cross-source figure deduplication using semantic similarity."""

    def deduplicate(
        self,
        observations: list[ImpactObservation],
    ) -> list[CanonicalFigure]:
        """Group observations reporting the same figure."""
        clusters: list[list[ImpactObservation]] = []

        for obs in observations:
            matched = False
            for cluster in clusters:
                if self._is_same_figure(obs, cluster[0]):
                    cluster.append(obs)
                    matched = True
                    break
            if not matched:
                clusters.append([obs])

        return [
            CanonicalFigure(
                value=max(obs.figures.get(key, 0) for obs in cluster for key in obs.figures),
                source_count=len(cluster),
                confidence="high" if len(cluster) >= 2 else cluster[0].confidence,
                latest_source=max(cluster, key=lambda o: o.temporal.published_at or datetime.min),
                all_sources=[o.source_url for o in cluster],
            )
            for cluster in clusters
        ]

    def _is_same_figure(self, a: ImpactObservation, b: ImpactObservation) -> bool:
        """Check if two observations report the same underlying figure."""
        # Same geo area + same figure key + similar value (within 10%)
        if a.geo_area.lower() != b.geo_area.lower():
            return False
        for key in a.figures:
            if key in b.figures:
                ratio = min(a.figures[key], b.figures[key]) / max(a.figures[key], b.figures[key], 1)
                if ratio > 0.9:
                    return True
        return False
```

### 5.4 Enhancement: Expanded Gazetteers

Priority countries to add (based on OCHA operations):

| Country | Admin 1 Count | Admin 2 Count | Source |
|---------|--------------|---------------|--------|
| **Ethiopia** | 12 regions | ~100 zones/woredas | OCHA boundaries |
| **Somalia** | 18 regions | ~90 districts | OCHA boundaries |
| **Sudan** | 18 states | ~190 localities | OCHA boundaries |
| **South Sudan** | 10 states | ~80 counties | OCHA boundaries |
| **DRC** | 26 provinces | ~150 territories | OCHA boundaries |
| **Afghanistan** | 34 provinces | ~400 districts | OCHA boundaries |
| **Yemen** | 22 governorates | ~333 districts | OCHA boundaries |
| **Syria** | 14 governorates | ~65 districts | OCHA boundaries |

**Implementation**: Create a `gazetteers/` directory with JSON files per country, loaded dynamically.

```
config/gazetteers/
  ethiopia.json
  somalia.json
  sudan.json
  south_sudan.json
  drc.json
  afghanistan.json
  yemen.json
  syria.json
```

### 5.5 Enhancement: Source Credibility Tiers

```python
SOURCE_CREDIBILITY = {
    "tier_1": {  # Primary: direct observation or official statistics
        "connectors": ["reliefweb"],
        "source_labels": ["OCHA", "WFP", "UNHCR", "WHO", "UNICEF", "IOM"],
        "weight": 1.0,
    },
    "tier_2": {  # Secondary: analysis and reporting
        "connectors": ["un", "ngo"],
        "source_labels": ["IFRC", "MSF", "Save the Children", "Oxfam", "IRC"],
        "weight": 0.8,
    },
    "tier_3": {  # Tertiary: media and aggregation
        "connectors": ["local_news", "government", "feed_base"],
        "source_labels": [],  # any
        "weight": 0.5,
    },
}
```

### 5.6 Enhancement: Multi-Impact Type per Evidence

Currently, each evidence item produces exactly one `ImpactObservation`. But a single Flash Update might mention deaths, displacement, infrastructure damage, and crop loss. Change to:

```python
# Current: single impact
impact_type = _classify_impact_type(combined)
graph.add_impact(ImpactObservation(..., impact_type=impact_type))

# Proposed: multiple impacts per evidence
impact_types = _classify_all_impact_types(combined)  # returns list
for itype in impact_types:
    graph.add_impact(ImpactObservation(..., impact_type=itype))
```

---

## 6. Date & Geo Awareness Strategy

### 6.1 Date Awareness

#### 6.1.1 Current State

- `SourceClaim.published_at` exists but is rarely populated
- Evidence digest sent to LLM omits dates
- SA output has no "as of" dating
- No temporal filtering or ordering of evidence

#### 6.1.2 Proposed Changes

**A. Evidence layer — carry dates through the pipeline:**

```python
# In build_ontology_from_evidence():
graph.add_claim(SourceClaim(
    published_at=ev.get("published_at"),         # ← already stored
    # ADD:
    event_date=ev.get("event_date"),             # when the event happened
    data_cutoff=ev.get("data_cutoff"),           # "data as of" date
))
```

**B. LLM evidence digest — include dates:**

```python
# In _generate_llm_narratives():
evidence_digest.append({
    "title": ev.get("title", ""),
    "country": ev.get("country", ""),
    "summary": ev.get("summary", "")[:200],
    "severity": ev.get("severity", ""),
    "connector": ev.get("connector", ""),
    "published_at": ev.get("published_at", ""),    # ← ADD
    "source_label": ev.get("source_label", ""),    # ← ADD
})
```

**C. SA output — "as of" dating:**

Every section should include the data cut-off date:
> **Key Figures** *(as of 18 February 2026)*
> - 48,000 people displaced (OCHA, 17 Feb 2026)
> - 23 deaths confirmed (Government, 16 Feb 2026)

**D. Temporal ordering:**

Sort evidence by date and prioritize recent sources. Stale evidence (>14 days for acute crises) gets a lower weight.

#### 6.1.3 Date Extraction Enhancement

Current ReliefWeb date extraction is fragile:
```python
date_str = date_map.get("original") or date_map.get("created") or date_map.get("changed")
```

Enhance with:
- `date.original` → event date (when the disaster started)
- `date.created` → publication date (when the report was published)
- Both should be preserved and carried through the pipeline

### 6.2 Geo Awareness

#### 6.2.1 Current State

- Admin detection uses keyword matching against gazetteers (word-boundary regex)
- Only Madagascar and Mozambique have gazetteers
- Evidence items get `admin_level=0` (country level) when no admin match is found
- This means ALL Ethiopia evidence collapses to country level

#### 6.2.2 Proposed Changes

**A. LLM-based NER for admin areas (Agent 2):**

For countries without gazetteers, use the Triage Agent to extract admin areas:

```python
# Triage agent prompt extract:
"For each evidence item, extract all geographic locations mentioned:
- country: the country name
- admin1: the province/region/state (if mentioned)
- admin2: the district/zone/woreda (if mentioned)
- specific_locations: any specific towns, camps, or facilities mentioned
Use your knowledge of administrative boundaries to classify correctly."
```

**B. Dynamic gazetteer from LLM extractions:**

Build a gazetteer dynamically from LLM NER results across multiple evidence items. If 3+ sources mention "Tigray Region" and "Mekelle", build the hierarchy automatically.

**C. OCHA API for admin boundaries:**

Use ReliefWeb's Locations API (`/v2/countries/{id}/locations`) to fetch admin boundaries programmatically for any country.

---

## 7. LLM Prompt Engineering Improvements

### 7.1 Current Prompt Problems

| Problem | Current | Impact |
|---------|---------|--------|
| No JSON schema on SA call | Free-form text parsed as JSON | Frequent parse failures, garbage output |
| Single system prompt for all sections | One prompt generates exec summary, 6 sectors, forecast, etc. | Each section gets diluted attention |
| Evidence truncated to 200 chars | `summary[:200]` | Loses critical detail — figures, dates, locations |
| No OCHA style guide | "Write concise, factual humanitarian prose" | Output doesn't match OCHA writing standards |
| No examples | No few-shot examples provided | Model guesses format and style |
| No date context | Dates omitted from evidence digest | Model can't provide temporal analysis |

### 7.2 Improved Prompt Architecture

#### 7.2.1 System Prompt — Shared Across All Agents

```
You are a senior OCHA Information Management Officer writing a Situation Analysis
for a humanitarian crisis. Your writing must follow OCHA reporting standards:

STYLE RULES:
- Use active voice and direct statements
- Lead with impact numbers, not process descriptions
- Always cite sources with [Source Name, Date] format
- Use "as of [Date]" for all quantitative figures
- Distinguish between "confirmed" and "estimated" figures
- Flag data gaps explicitly rather than omitting them
- Use IPC/CH phase language for food security
- Use Sphere standards references for sector analysis

FACTUAL RULES:
- ONLY use information from the provided evidence items
- NEVER invent figures, dates, or facts not in the evidence
- If evidence is insufficient for a section, state "Data pending" with specific gaps
- When figures differ between sources, report the range and note the discrepancy
- Attribute every claim to its source
```

#### 7.2.2 Per-Sector Prompts

Each sector agent gets a tailored prompt with sector-specific guidance:

**Food Security example:**
```
You are analyzing the FOOD SECURITY sector for this crisis.

Focus on:
- IPC/CH phase classification if available
- Number of food insecure people by severity
- Crop/harvest impact
- Market disruption and food price changes
- Nutrition screening results (GAM/SAM rates)
- WFP/FAO response activities

Structure your output as:
{
  "table_data": [
    {"area": "...", "population_affected": ..., "ipc_phase": ..., "key_needs": "..."}
  ],
  "narrative": "...",
  "key_messages": ["...", "..."],
  "data_gaps": ["...", "..."]
}
```

#### 7.2.3 Structured Output via JSON Schema

Replace free-form JSON with strict schema enforcement:

```python
schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["executive_summary", "national_impact", "sectors", "forecast"],
    "properties": {
        "executive_summary": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": 3000},
                "key_figures": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "value": {"type": "string"},
                            "source": {"type": "string"},
                            "as_of_date": {"type": "string"},
                        },
                    },
                },
            },
        },
        # ... per-sector schemas ...
    },
}

body = {
    "model": get_openai_model(),
    "input": [...],
    "text": {
        "format": {
            "type": "json_schema",
            "name": "situation_analysis",
            "schema": schema,
            "strict": True,
        }
    },
}
```

### 7.3 Evidence Window Improvement

**Current**: 30 items × 200-char summaries = ~6,000 chars of context
**Proposed**: 50 items × 500-char summaries + dates + geo tags = ~30,000 chars of context

This fits comfortably within gpt-4.1's 1M token context window.

### 7.4 Few-Shot Examples

Include 1-2 exemplar sections in the system prompt from real OCHA outputs:

```
EXAMPLE — Executive Summary for Cyclone Freddy (Mozambique, March 2023):
"As of 21 March 2023, Tropical Cyclone Freddy has affected an estimated
1.2 million people across six provinces in southern Mozambique [OCHA, 21 Mar].
The death toll stands at 167 confirmed, with 423 injured and 89 still missing
[Government of Mozambique, 20 Mar]. Zambezia and Sofala provinces are most
severely affected, with 287,000 people displaced and currently sheltering in
149 temporary accommodation centres [IOM DTM, 19 Mar]..."
```

---

## 8. Model Selection Analysis

### 8.1 Current State

All LLM calls use `gpt-4.1-mini` — a single model for everything.

### 8.2 Proposed Model Matrix

| Agent / Task | Recommended Model | Reasoning |
|-------------|-------------------|-----------|
| **Per-event enrichment** | `gpt-4.1-mini` | Classification task, strict schema — mini is sufficient and fast |
| **Evidence Triage (Agent 2)** | `gpt-4.1-mini` | NER + classification — mini handles this well |
| **Entity Linking (Agent 3)** | `gpt-4.1-mini` | Structured matching — mini sufficient |
| **Sector Analysts (Agent 4)** | `gpt-4.1` | Synthesis + OCHA writing — needs full model quality |
| **Synthesis / QA (Agent 5)** | `gpt-4.1` | Executive-facing output — highest quality needed |
| **PDF OCR interpretation** | Not LLM (Docling) | OCR is not an LLM task |

### 8.3 Model Alternatives

| Model | Provider | Strengths | Weaknesses | Cost (1M tokens) |
|-------|----------|-----------|------------|-------------------|
| `gpt-4.1` | OpenAI | Best structured output, great at following complex instructions | Expensive | $2 input / $8 output |
| `gpt-4.1-mini` | OpenAI | Fast, cheap, good at classification | Less nuanced writing | $0.40 input / $1.60 output |
| `gpt-4.1-nano` | OpenAI | Cheapest, fastest | Limited reasoning | $0.10 input / $0.40 output |
| `claude-sonnet-4` | Anthropic | Excellent humanitarian knowledge, careful reasoning | Different API format | $3 input / $15 output |
| `gemini-2.5-flash` | Google | Massive context (1M tokens), fast, cheap | Variable quality | $0.15 input / $0.60 output |
| `llama-3.3-70b` | Meta (local) | Free, private, good quality | Requires GPU, no JSON schema mode | Free (GPU cost) |

### 8.4 Recommendation

- **Keep OpenAI** for now — the Responses API structured output with `strict: true` is a critical quality feature that other providers don't match
- **Use `gpt-4.1`** for synthesis tasks (sector analysis, executive summary) where writing quality matters
- **Use `gpt-4.1-mini`** for classification tasks (triage, entity linking, per-event enrichment)
- **Consider `gpt-4.1-nano`** for high-volume, simple tasks (e.g., date extraction, relevance scoring)
- **Future**: Add provider abstraction layer so we can switch models per agent

### 8.5 Environment Variable Design

```bash
# Current (single model):
OPENAI_MODEL=gpt-4.1-mini

# Proposed (per-agent model selection):
OPENAI_MODEL=gpt-4.1-mini                # default / fallback
OPENAI_MODEL_TRIAGE=gpt-4.1-mini         # evidence triage agent
OPENAI_MODEL_ENTITY=gpt-4.1-mini         # entity linking agent
OPENAI_MODEL_SECTOR=gpt-4.1              # sector analyst agents
OPENAI_MODEL_SYNTHESIS=gpt-4.1           # synthesis / QA agent
OPENAI_MODEL_ENRICHMENT=gpt-4.1-mini     # per-event enrichment
```

---

## 9. Implementation Roadmap

### Phase 1: Quick Wins (1-2 days)

These fix the worst SA output problems with minimal code changes:

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 1.1 | **Add Ethiopia gazetteer** to `graph_ontology.py` | Admin tables populated | 30 min |
| 1.2 | **Fix event name inference** — add conflict/epidemic/drought patterns | "Unknown Event" → "Ethiopia Crisis" | 30 min |
| 1.3 | **Add dates to evidence digest** sent to LLM | Date-aware narratives | 15 min |
| 1.4 | **Add source_label to evidence digest** | Source attribution in output | 15 min |
| 1.5 | **Add JSON schema to SA LLM call** | Reliable structured output | 1 hour |
| 1.6 | **Fix country substring matching** (Niger/Nigeria) | Eliminate cross-contamination | 15 min |
| 1.7 | **Improve sector table rendering** — truncate and label evidence properly | Less garbage in tables | 1 hour |

### Phase 2: OCR Pipeline (3-5 days)

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 2.1 | Install Docling + Tesseract dependencies | OCR capability | 1 hour |
| 2.2 | Create `pdf_extraction.py` module | PDF → structured text | 1 day |
| 2.3 | Wire PDF extraction into ReliefWeb connector | ReliefWeb PDFs extracted | 1 day |
| 2.4 | Add ReliefWeb pagination | Access beyond 200 results | 2 hours |
| 2.5 | Enhance ReliefWeb query (format filters, full fields) | Better evidence selection | 2 hours |
| 2.6 | Test with Ethiopia Flash Updates | Validate pipeline end-to-end | 1 day |

### Phase 3: Multi-Agent Architecture (5-8 days)

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 3.1 | Create agent base class with retry/fallback | Architecture foundation | 1 day |
| 3.2 | Implement Evidence Triage Agent | Date + Geo NER | 1 day |
| 3.3 | Implement Entity Linking Agent | Figure dedup, cross-ref | 1 day |
| 3.4 | Implement Sector Analyst Agents (6) | Quality sector output | 2 days |
| 3.5 | Implement Synthesis / QA Agent | Coherent executive output | 1 day |
| 3.6 | Wire agents into coordinator pipeline | End-to-end integration | 1 day |
| 3.7 | Add per-agent model selection | Cost optimization | 2 hours |

### Phase 4: Graph RAG Deep Enhancement (5-7 days)

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 4.1 | Add temporal layer to graph nodes | Time-aware analysis | 1 day |
| 4.2 | Implement figure deduplication | Accurate national figures | 1 day |
| 4.3 | Add multi-impact per evidence | Complete impact picture | 1 day |
| 4.4 | Expand gazetteers (Ethiopia, Somalia, Sudan, etc.) | Admin detection for 8+ countries | 1 day |
| 4.5 | Add source credibility tiers | Weighted evidence | 2 hours |
| 4.6 | Dynamic gazetteer from LLM NER | Any country support | 1 day |
| 4.7 | Entity linking across evidence items | Deduplicated entities | 1 day |

### Phase 5: Polish & Documentation (2-3 days)

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 5.1 | Update specs/15-llm-intelligence-layer-v1.md | Architecture documentation | 2 hours |
| 5.2 | Update progress.md | Progress tracking | 30 min |
| 5.3 | Add few-shot OCHA examples to prompts | Writing quality | 2 hours |
| 5.4 | Add SA quality evaluation metrics | Measurable improvement | 1 day |
| 5.5 | E2E regression test for SA | Prevent regression | 1 day |

---

## Appendix A: Evidence Flow — Current vs. Proposed

### Current Flow

```
Sources → Connectors → DB → build_graph_context() → evidence[]
                                                         │
                                                    graph_ontology.py
                                                    (keyword NLP only)
                                                         │
                                                    situation_analysis.py
                                                         │
                                            ┌────────────┼────────────┐
                                            │            │            │
                                      Deterministic   Single LLM    Output
                                      rendering       call (no      (Markdown)
                                      (raw evidence   schema)
                                       in tables)
```

### Proposed Flow

```
Sources → Connectors → DB → build_graph_context() → evidence[]
                  ↕                                       │
            PDF Extraction                          Triage Agent
            (Docling/OCR)                          (date, geo, classify)
                                                         │
                                                    Entity Link Agent
                                                    (dedup, link, temporal)
                                                         │
                                                  Enhanced Ontology Graph
                                                  (temporal, deduplicated)
                                                         │
                                         ┌───────────────┼───────────────┐
                                         │               │               │
                                    Sector Agents    Sector Agents   Sector Agents
                                    (Shelter, WASH)  (Health, Food)  (Prot, Edu)
                                         │               │               │
                                         └───────────────┼───────────────┘
                                                         │
                                                  Synthesis Agent
                                                  (executive summary,
                                                   cross-reference,
                                                   consistency check)
                                                         │
                                                    Output (Markdown)
                                                    (dated, sourced,
                                                     OCHA quality)
```

## Appendix B: Risk Analysis

| Risk | Mitigation |
|------|-----------|
| Multi-agent latency (5+ LLM calls) | Parallelize sector agents; async calls |
| Cost increase ($0.01 → $0.50 per SA) | Per-agent model selection; cache triage results |
| OCR quality on complex layouts | Tiered approach (Docling → Tesseract → manual review flag) |
| LLM hallucination in sector analysis | Citation locking; QA agent cross-checks against evidence |
| Gazetteer maintenance burden | Dynamic gazetteer from LLM NER + OCHA API boundaries |
| Rate limiting on OpenAI API | Batch calls; add delay between agents; retry with backoff |

## Appendix C: Quick Reference — Key Files to Modify

| File | Changes Needed |
|------|---------------|
| `src/agent_hum_crawler/situation_analysis.py` | JSON schema on LLM call, improve sector rendering, date awareness |
| `src/agent_hum_crawler/graph_ontology.py` | Ethiopia gazetteer, temporal layer, figure dedup, multi-impact |
| `src/agent_hum_crawler/connectors/reliefweb.py` | PDF extraction, pagination, enhanced query |
| `src/agent_hum_crawler/coordinator.py` | Wire multi-agent pipeline, per-agent model selection |
| `src/agent_hum_crawler/taxonomy.py` | Fix country substring matching (word-boundary) |
| `src/agent_hum_crawler/llm_enrichment.py` | No changes — already well-structured with schema |
| **NEW: `src/agent_hum_crawler/pdf_extraction.py`** | Docling/Tesseract PDF OCR module |
| **NEW: `src/agent_hum_crawler/agents/`** | Agent base class + specialized agents |
| **NEW: `config/gazetteers/`** | Per-country admin boundary JSON files |

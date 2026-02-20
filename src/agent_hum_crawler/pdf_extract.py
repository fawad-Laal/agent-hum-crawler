"""PDF text and table extraction service.

Extracts text *and* structured tables from PDF documents using pdfplumber
(primary) with pypdf fallback.  Returns either a plain-text string
(``extract_pdf_text``) or a rich ``ExtractedDocument`` with tables
(``extract_pdf_document``).

Usage::

    from agent_hum_crawler.pdf_extract import extract_pdf_text, extract_pdf_document
    text = extract_pdf_text("https://example.com/report.pdf")
    doc  = extract_pdf_document("https://example.com/report.pdf")
    for tbl in doc.tables:
        print(tbl.to_markdown())
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Maximum PDF size we'll download (20 MB).
_MAX_PDF_BYTES = 20 * 1024 * 1024

# Maximum pages to extract (keeps memory bounded).
_MAX_PAGES = 80


# ── Structured result types ──────────────────────────────────────────


@dataclass
class ExtractedTable:
    """A single table extracted from a PDF page."""

    page_number: int
    headers: list[str]
    rows: list[list[str]]

    def to_markdown(self) -> str:
        """Render the table as a Markdown table string."""
        if not self.headers and not self.rows:
            return ""
        cols = self.headers or [f"col{i}" for i in range(len(self.rows[0]))] if self.rows else self.headers
        lines = ["| " + " | ".join(cols) + " |"]
        lines.append("| " + " | ".join("---" for _ in cols) + " |")
        for row in self.rows:
            # Pad row to column count
            padded = list(row) + [""] * max(0, len(cols) - len(row))
            lines.append("| " + " | ".join(padded[: len(cols)]) + " |")
        return "\n".join(lines)


@dataclass
class ExtractedDocument:
    """Rich extraction result containing text, tables, and metadata."""

    text: str = ""
    tables: list[ExtractedTable] = field(default_factory=list)
    page_count: int = 0
    extraction_method: str = ""  # "pdfplumber", "pypdf", or ""

    @property
    def has_tables(self) -> bool:
        return len(self.tables) > 0

    def tables_as_text(self) -> str:
        """Format all tables as Markdown text for downstream NLP."""
        parts: list[str] = []
        for i, tbl in enumerate(self.tables, 1):
            md = tbl.to_markdown()
            if md:
                parts.append(f"[Table {i} – page {tbl.page_number}]\n{md}")
        return "\n\n".join(parts)

    @property
    def full_text(self) -> str:
        """Text + table text combined for figure extraction."""
        tbl_text = self.tables_as_text()
        if tbl_text:
            return self.text + "\n\n" + tbl_text
        return self.text


# ── Public API ───────────────────────────────────────────────────────


def extract_pdf_document(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
    max_bytes: int = _MAX_PDF_BYTES,
    max_pages: int = _MAX_PAGES,
) -> ExtractedDocument:
    """Download a PDF from *url* and return structured ``ExtractedDocument``.

    Returns an empty ``ExtractedDocument`` on any failure so callers can
    safely ignore PDFs that don't cooperate.
    """
    try:
        pdf_bytes = _download(url, client=client, timeout=timeout, max_bytes=max_bytes)
        if not pdf_bytes:
            return ExtractedDocument()
        doc = _extract_pdfplumber_doc(pdf_bytes, max_pages=max_pages)
        if not doc.text:
            fallback_text = _extract_pypdf(pdf_bytes, max_pages=max_pages)
            doc = ExtractedDocument(
                text=fallback_text,
                tables=doc.tables,  # keep any tables found
                page_count=doc.page_count,
                extraction_method="pypdf" if fallback_text else "",
            )
        return doc
    except Exception:
        logger.debug("PDF extraction failed for %s", url, exc_info=True)
        return ExtractedDocument()


def extract_pdf_text(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
    max_bytes: int = _MAX_PDF_BYTES,
    max_pages: int = _MAX_PAGES,
) -> str:
    """Download a PDF from *url* and return its full text.

    Backward-compatible wrapper around :func:`extract_pdf_document`.
    Returns an empty string on any failure (network, parsing, etc.)
    so callers can safely ignore PDFs that don't cooperate.
    """
    doc = extract_pdf_document(
        url, client=client, timeout=timeout, max_bytes=max_bytes, max_pages=max_pages,
    )
    return doc.full_text.strip()


# ── Internal helpers ─────────────────────────────────────────────────


def _download(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
    max_bytes: int = _MAX_PDF_BYTES,
) -> bytes | None:
    """Download a PDF, respecting *max_bytes*."""
    try:
        if client is not None:
            r = client.get(url)
        else:
            with httpx.Client(timeout=timeout) as c:
                r = c.get(url)
        r.raise_for_status()
        if len(r.content) > max_bytes:
            logger.warning("PDF too large (%d bytes): %s", len(r.content), url)
            return None
        return r.content
    except Exception:
        logger.debug("Failed to download PDF: %s", url, exc_info=True)
        return None


def _normalise_cell(cell: Any) -> str:
    """Normalise a raw pdfplumber table cell to a string."""
    if cell is None:
        return ""
    return str(cell).strip().replace("\n", " ")


def _extract_pdfplumber_doc(
    data: bytes, *, max_pages: int = _MAX_PAGES,
) -> ExtractedDocument:
    """Extract text *and* tables using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        return ExtractedDocument()

    pages_text: list[str] = []
    tables: list[ExtractedTable] = []
    page_count = 0

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        with pdfplumber.open(tmp_path) as pdf:
            page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                if i >= max_pages:
                    break

                # ── Text extraction ──
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text.strip())

                # ── Table extraction ──
                try:
                    raw_tables = page.extract_tables() or []
                except Exception:
                    raw_tables = []

                for raw_tbl in raw_tables:
                    if not raw_tbl or len(raw_tbl) < 2:
                        continue  # need at least header + 1 data row
                    header_row = [_normalise_cell(c) for c in raw_tbl[0]]
                    data_rows = [
                        [_normalise_cell(c) for c in row]
                        for row in raw_tbl[1:]
                        if any(_normalise_cell(c) for c in row)
                    ]
                    if data_rows:
                        tables.append(ExtractedTable(
                            page_number=i + 1,
                            headers=header_row,
                            rows=data_rows,
                        ))
    except Exception:
        logger.debug("pdfplumber extraction failed", exc_info=True)
        return ExtractedDocument()
    finally:
        tmp_path.unlink(missing_ok=True)

    return ExtractedDocument(
        text="\n\n".join(pages_text),
        tables=tables,
        page_count=page_count,
        extraction_method="pdfplumber",
    )


def _extract_pypdf(data: bytes, *, max_pages: int = _MAX_PAGES) -> str:
    """Fallback extraction using pypdf."""
    try:
        from pypdf import PdfReader
        import io
    except ImportError:
        return ""

    pages_text: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(data))
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages_text.append(page_text.strip())
    except Exception:
        logger.debug("pypdf extraction failed", exc_info=True)
        return ""

    return "\n\n".join(pages_text)

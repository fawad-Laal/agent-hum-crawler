"""MIME-first attachment text extraction service (Phase 9.2).

Routing table
─────────────
  PDF  (application/pdf, .pdf)                  → MarkItDown → pdfplumber → pypdf
  DOCX (application/...wordprocessingml.document,
        application/msword, .docx, .doc)         → MarkItDown
  XLSX (application/...spreadsheetml.sheet,
        application/vnd.ms-excel, .xlsx, .xls)   → MarkItDown
  HTML (text/html, application/xhtml+xml,
        .html, .htm)                              → trafilatura → bs4
  Unknown / unsupported                          → skipped (empty result, method="skipped")

MarkItDown is imported lazily — graceful fallback if the package is not installed.
For PDFs the fallback chain is: MarkItDown → pdfplumber → pypdf.
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Re-use the rich result type and PDF fallback helpers from pdf_extract.
from .pdf_extract import (
    ExtractedDocument,
    _MAX_PAGES,
    _extract_pdfplumber_doc,
    _extract_pypdf,
)

logger = logging.getLogger(__name__)

_MAX_ATTACH_BYTES = 20 * 1024 * 1024  # 20 MB

# ── MIME routing tables ───────────────────────────────────────────────

_MIME_TO_DOCTYPE: dict[str, str] = {
    "application/pdf": "document_pdf",
    "application/x-pdf": "document_pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document_docx",
    "application/msword": "document_docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document_xlsx",
    "application/vnd.ms-excel": "document_xlsx",
    "text/html": "document_html",
    "application/xhtml+xml": "document_html",
}

_EXT_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".html": "text/html",
    ".htm": "text/html",
}

_DOCTYPE_TO_SUFFIX: dict[str, str] = {
    "document_pdf": ".pdf",
    "document_docx": ".docx",
    "document_xlsx": ".xlsx",
}


# ── Public helpers ────────────────────────────────────────────────────


def resolve_mime(
    *,
    declared_mime: str | None,
    filename: str | None,
    url: str,
) -> str | None:
    """Return a normalised MIME string: declared → filename ext → URL ext.

    Strips parameters (e.g. ``"application/pdf; charset=utf-8"``).
    Returns ``None`` when none of the three signals are recognised.
    """
    if declared_mime:
        return declared_mime.split(";")[0].strip().lower()
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix in _EXT_TO_MIME:
            return _EXT_TO_MIME[suffix]
    try:
        parsed_path = urlparse(url).path
        suffix = Path(parsed_path).suffix.lower()
        if suffix in _EXT_TO_MIME:
            return _EXT_TO_MIME[suffix]
    except Exception:
        pass
    return None


def mime_to_doctype(mime: str | None) -> str | None:
    """Map a MIME string to a ``ContentSource.type`` literal, or ``None`` if unsupported."""
    if not mime:
        return None
    return _MIME_TO_DOCTYPE.get(mime.split(";")[0].strip().lower())


# ── Main public API ───────────────────────────────────────────────────


def extract_attachment(
    url: str,
    *,
    declared_mime: str | None = None,
    filename: str | None = None,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
    max_bytes: int = _MAX_ATTACH_BYTES,
    max_pages: int = _MAX_PAGES,
) -> ExtractedDocument:
    """Download and extract text from an attachment using MIME-first routing.

    Returns an ``ExtractedDocument`` in all circumstances:
    - ``extraction_method="skipped"`` for unsupported / unknown types (no download).
    - ``extraction_method="none"``    when download fails or yields no bytes.
    - Otherwise the method reflects the extractor that succeeded.
    """
    t0 = time.monotonic()

    mime = resolve_mime(declared_mime=declared_mime, filename=filename, url=url)
    doc_type = _MIME_TO_DOCTYPE.get(mime or "")

    if doc_type is None:
        logger.debug("Skipping unsupported attachment mime=%s url=%s", mime, url)
        return ExtractedDocument(
            extraction_method="skipped",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

    data = _download_attachment(url, client=client, timeout=timeout, max_bytes=max_bytes)
    if not data:
        return ExtractedDocument(
            extraction_method="none",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

    if doc_type == "document_html":
        doc = _extract_html(data)
    elif doc_type in ("document_docx", "document_xlsx"):
        doc = _extract_with_markitdown(data, suffix=_DOCTYPE_TO_SUFFIX.get(doc_type, ".bin"))
    else:  # document_pdf — MarkItDown → pdfplumber → pypdf
        doc = _extract_pdf(data, max_pages=max_pages)

    doc.duration_ms = int((time.monotonic() - t0) * 1000)
    return doc


# ── Internal helpers ──────────────────────────────────────────────────


def _download_attachment(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
    max_bytes: int = _MAX_ATTACH_BYTES,
) -> bytes | None:
    """Download attachment bytes, enforcing *max_bytes* size limit."""
    try:
        if client is not None:
            r = client.get(url)
        else:
            with httpx.Client(timeout=timeout) as c:
                r = c.get(url)
        r.raise_for_status()
        if len(r.content) > max_bytes:
            logger.warning("Attachment too large (%d bytes): %s", len(r.content), url)
            return None
        return r.content
    except Exception:
        logger.debug("Failed to download attachment: %s", url, exc_info=True)
        return None


def _try_markitdown(data: bytes, *, suffix: str) -> str:
    """Lazy-import MarkItDown and convert *data* bytes to Markdown text.

    Returns an empty string if MarkItDown is not installed or conversion fails.
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        logger.debug("markitdown not installed — skipping MarkItDown path")
        return ""
    tmp_path = Path(tempfile.mktemp(suffix=suffix))
    try:
        tmp_path.write_bytes(data)
        md = MarkItDown()
        result = md.convert(str(tmp_path))
        return (result.text_content or "").strip()
    except Exception:
        logger.debug("MarkItDown extraction failed for suffix=%s", suffix, exc_info=True)
        return ""
    finally:
        tmp_path.unlink(missing_ok=True)


def _extract_with_markitdown(data: bytes, *, suffix: str) -> ExtractedDocument:
    """MarkItDown-only extraction for DOCX and XLSX (no legacy fallback)."""
    text = _try_markitdown(data, suffix=suffix)
    method = "markitdown" if text else ""
    return ExtractedDocument(text=text, extraction_method=method)


def _extract_pdf(data: bytes, *, max_pages: int = _MAX_PAGES) -> ExtractedDocument:
    """MarkItDown → pdfplumber → pypdf fallback chain for PDFs."""
    # 1. Try MarkItDown (fast, handles scanned + structured PDFs)
    text = _try_markitdown(data, suffix=".pdf")
    if text:
        return ExtractedDocument(text=text, extraction_method="markitdown")

    # 2. pdfplumber (table-aware)
    doc = _extract_pdfplumber_doc(data, max_pages=max_pages)
    if doc.text:
        return doc

    # 3. pypdf final fallback
    fallback_text = _extract_pypdf(data, max_pages=max_pages)
    return ExtractedDocument(
        text=fallback_text,
        tables=doc.tables,
        page_count=doc.page_count,
        extraction_method="pypdf" if fallback_text else "",
    )


def _extract_html(data: bytes) -> ExtractedDocument:
    """trafilatura → bs4 HTML extraction."""
    import trafilatura
    from bs4 import BeautifulSoup

    html = data.decode("utf-8", errors="replace")
    extracted = trafilatura.extract(html)
    if extracted and extracted.strip():
        return ExtractedDocument(text=extracted.strip(), extraction_method="trafilatura")
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return ExtractedDocument(text=text, extraction_method="bs4" if text else "")

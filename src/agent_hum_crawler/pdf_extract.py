"""PDF text extraction service.

Extracts text from PDF documents using pdfplumber (primary) with pypdf
fallback.  Downloads the PDF to a temporary file, extracts text from all
pages, and returns a single plain-text string.

Usage::

    from agent_hum_crawler.pdf_extract import extract_pdf_text
    text = extract_pdf_text("https://example.com/report.pdf")
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Maximum PDF size we'll download (20 MB).
_MAX_PDF_BYTES = 20 * 1024 * 1024

# Maximum pages to extract (keeps memory bounded).
_MAX_PAGES = 80


def extract_pdf_text(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 60.0,
    max_bytes: int = _MAX_PDF_BYTES,
    max_pages: int = _MAX_PAGES,
) -> str:
    """Download a PDF from *url* and return its full text.

    Returns an empty string on any failure (network, parsing, etc.)
    so callers can safely ignore PDFs that don't cooperate.
    """
    try:
        pdf_bytes = _download(url, client=client, timeout=timeout, max_bytes=max_bytes)
        if not pdf_bytes:
            return ""
        text = _extract_pdfplumber(pdf_bytes, max_pages=max_pages)
        if not text:
            text = _extract_pypdf(pdf_bytes, max_pages=max_pages)
        return text.strip()
    except Exception:
        logger.debug("PDF extraction failed for %s", url, exc_info=True)
        return ""


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


def _extract_pdfplumber(data: bytes, *, max_pages: int = _MAX_PAGES) -> str:
    """Extract text using pdfplumber (good for tables and text)."""
    try:
        import pdfplumber
    except ImportError:
        return ""

    pages_text: list[str] = []
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        with pdfplumber.open(tmp_path) as pdf:
            for i, page in enumerate(pdf.pages):
                if i >= max_pages:
                    break
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text.strip())
    except Exception:
        logger.debug("pdfplumber extraction failed", exc_info=True)
        return ""
    finally:
        tmp_path.unlink(missing_ok=True)

    return "\n\n".join(pages_text)


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

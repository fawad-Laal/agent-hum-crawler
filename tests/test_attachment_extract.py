"""Tests for Phase 9.2 — MIME-first attachment extraction (attachment_extract.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from agent_hum_crawler.attachment_extract import (
    _EXT_TO_MIME,
    _MIME_TO_DOCTYPE,
    extract_attachment,
    mime_to_doctype,
    resolve_mime,
)
from agent_hum_crawler.pdf_extract import ExtractedDocument


# ── resolve_mime ──────────────────────────────────────────────────────


class TestResolveMime:
    def test_declared_mime_wins(self) -> None:
        assert resolve_mime(
            declared_mime="application/pdf",
            filename="report.docx",  # would be docx without declared
            url="https://example.org/file.xlsx",  # would be xlsx without declared
        ) == "application/pdf"

    def test_declared_mime_strips_parameters(self) -> None:
        assert resolve_mime(
            declared_mime="application/pdf; charset=utf-8",
            filename=None,
            url="https://example.org/file",
        ) == "application/pdf"

    def test_filename_fallback(self) -> None:
        assert resolve_mime(
            declared_mime=None,
            filename="annual_report.docx",
            url="https://example.org/file",
        ) == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_url_extension_fallback(self) -> None:
        assert resolve_mime(
            declared_mime=None,
            filename=None,
            url="https://reliefweb.int/files/report.pdf",
        ) == "application/pdf"

    def test_xlsx_url_extension(self) -> None:
        assert resolve_mime(
            declared_mime=None,
            filename=None,
            url="https://example.org/data.xlsx",
        ) == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_html_extension(self) -> None:
        assert resolve_mime(
            declared_mime=None,
            filename=None,
            url="https://example.org/page.html",
        ) == "text/html"

    def test_unknown_returns_none(self) -> None:
        assert resolve_mime(
            declared_mime=None,
            filename=None,
            url="https://example.org/file.xyz",
        ) is None

    def test_all_mime_extensions_covered(self) -> None:
        """Every key in _EXT_TO_MIME should round-trip through resolve_mime."""
        for ext, expected_mime in _EXT_TO_MIME.items():
            result = resolve_mime(
                declared_mime=None,
                filename=None,
                url=f"https://example.org/doc{ext}",
            )
            assert result == expected_mime, f"ext={ext}"


# ── mime_to_doctype ───────────────────────────────────────────────────


class TestMimeToDoctype:
    def test_pdf_maps_to_document_pdf(self) -> None:
        assert mime_to_doctype("application/pdf") == "document_pdf"

    def test_docx_maps_correctly(self) -> None:
        assert mime_to_doctype(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ) == "document_docx"

    def test_msword_maps_to_document_docx(self) -> None:
        assert mime_to_doctype("application/msword") == "document_docx"

    def test_xlsx_maps_correctly(self) -> None:
        assert mime_to_doctype(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ) == "document_xlsx"

    def test_html_maps_correctly(self) -> None:
        assert mime_to_doctype("text/html") == "document_html"

    def test_unknown_returns_none(self) -> None:
        assert mime_to_doctype("application/octet-stream") is None
        assert mime_to_doctype(None) is None

    def test_all_known_mimes_covered(self) -> None:
        """Every key in _MIME_TO_DOCTYPE should return a non-None doctype."""
        for mime in _MIME_TO_DOCTYPE:
            assert mime_to_doctype(mime) is not None, f"mime={mime}"


# ── extract_attachment — skipped / no-download paths ─────────────────


class TestExtractAttachmentSkipped:
    def test_unsupported_mime_returns_skipped(self) -> None:
        doc = extract_attachment(
            "https://example.org/file.bin",
            declared_mime="application/octet-stream",
        )
        assert doc.extraction_method == "skipped"
        assert doc.full_text == ""

    def test_unknown_extension_returns_skipped(self) -> None:
        doc = extract_attachment("https://example.org/file.xyz")
        assert doc.extraction_method == "skipped"
        assert doc.duration_ms >= 0

    def test_download_failure_returns_none_method(self) -> None:
        def fail_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        client = httpx.Client(transport=httpx.MockTransport(fail_handler))
        doc = extract_attachment(
            "https://example.org/report.pdf",
            client=client,
        )
        assert doc.extraction_method == "none"
        assert doc.full_text == ""

    def test_duration_ms_is_set(self) -> None:
        doc = extract_attachment("https://example.org/file.xyz")
        assert isinstance(doc.duration_ms, int)


# ── extract_attachment — with content ────────────────────────────────


class TestExtractAttachmentWithContent:
    def test_html_extraction_via_mock(self) -> None:
        """HTML attachment is extracted via trafilatura/bs4."""
        html_bytes = b"<html><body><p>Flood damaged 5000 homes in Sindh.</p></body></html>"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=html_bytes)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        doc = extract_attachment(
            "https://example.org/report.html",
            client=client,
        )
        assert doc.full_text != ""
        assert "flood" in doc.full_text.lower() or "5000" in doc.full_text
        assert doc.extraction_method in ("trafilatura", "bs4")

    def test_pdf_mime_fallback_to_pdfplumber_on_markitdown_failure(self) -> None:
        """When MarkItDown fails, pdfplumber fallback is tried.

        We mock _try_markitdown to avoid the magika/dotenv side-effect and
        to deterministically exercise the pdfplumber fallback path.
        """
        from unittest.mock import patch

        import httpx

        from agent_hum_crawler.attachment_extract import extract_attachment

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not-real-pdf-bytes")

        client = httpx.Client(transport=httpx.MockTransport(handler))

        # Mock MarkItDown returning empty to force the pdfplumber fallback path
        with patch("agent_hum_crawler.attachment_extract._try_markitdown", return_value=""):
            doc = extract_attachment(
                "https://example.org/report.pdf",
                client=client,
            )
        # Both MarkItDown (mocked empty) and pdfplumber will fail on garbage bytes.
        assert isinstance(doc, ExtractedDocument)
        assert isinstance(doc.duration_ms, int)

    def test_docx_mime_uses_markitdown_path(self) -> None:
        """DOCX type routes to MarkItDown path; gracefully empty without a real file.

        We mock _try_markitdown to avoid triggering the real MarkItDown/magika
        import which calls load_dotenv() at import time and pollutes os.environ
        for subsequent tests.
        """
        from unittest.mock import patch

        import httpx

        from agent_hum_crawler.attachment_extract import extract_attachment

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"PK\x03\x04fake-docx-bytes")

        client = httpx.Client(transport=httpx.MockTransport(handler))

        # Patch _try_markitdown so MarkItDown/magika are never imported here
        with patch("agent_hum_crawler.attachment_extract._try_markitdown", return_value="") as mock_md:
            doc = extract_attachment(
                "https://example.org/report.docx",
                declared_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                client=client,
            )
            mock_md.assert_called_once()
            called_suffix = mock_md.call_args.kwargs.get("suffix", mock_md.call_args.args[1] if len(mock_md.call_args.args) > 1 else None)
            assert called_suffix == ".docx"

        assert isinstance(doc, ExtractedDocument)
        assert doc.extraction_method == ""  # MarkItDown returned empty → no text


# ── ReliefWeb connector integration — Phase 9.1 fields ───────────────


class TestReliefWebPhase91Integration:
    """Verify that headline/origin fields are extracted by the connector."""

    def test_headline_title_takes_precedence(self) -> None:
        """When headline.title is present, it is used over the raw title."""
        import json

        import httpx

        from agent_hum_crawler.config import RuntimeConfig
        from agent_hum_crawler.connectors.reliefweb import ReliefWebConnector

        class MockConnector(ReliefWebConnector):
            def __init__(self, client: httpx.Client):
                super().__init__(appname="approved-app")
                self._client = client

            def _build_client(self) -> httpx.Client:
                return self._client

        sample_payload = {
            "data": [
                {
                    "fields": {
                        "title": "Generic title",
                        "headline": {
                            "title": "Specific headline title",
                            "summary": "Summary of the situation.",
                        },
                        "url_alias": "https://reliefweb.int/report/pk/test",
                        "body-html": "<p>Body text about flooding.</p>",
                        "country": [{"name": "Pakistan"}],
                        "language": [{"code": "en"}],
                        "date": {"original": "2026-03-04T00:00:00+00:00"},
                        "origin": {"url": "https://ndma.gov.pk/report.html"},
                    }
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if "api.reliefweb.int" in str(request.url):
                return httpx.Response(200, json=sample_payload)
            return httpx.Response(200, text="<html><body>Flood details.</body></html>")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        connector = MockConnector(client=client)
        cfg = RuntimeConfig(countries=["Pakistan"], disaster_types=["flood"], check_interval_minutes=30)
        result = connector.fetch(config=cfg, limit=5, include_content=True)
        assert result.total_matched == 1
        item = result.items[0]

        # headline.title wins
        assert item.title == "Specific headline title"
        # headline.summary is in the text
        assert "summary of the situation" in item.text.lower()
        # origin URL is persisted
        assert item.origin_url == "https://ndma.gov.pk/report.html"

    def test_headline_absent_falls_back_to_title(self) -> None:
        """When headline is absent, the raw title is used."""
        import httpx

        from agent_hum_crawler.config import RuntimeConfig
        from agent_hum_crawler.connectors.reliefweb import ReliefWebConnector

        class MockConnector(ReliefWebConnector):
            def __init__(self, client: httpx.Client):
                super().__init__(appname="approved-app")
                self._client = client

            def _build_client(self) -> httpx.Client:
                return self._client

        sample_payload = {
            "data": [
                {
                    "fields": {
                        "title": "Fallback title",
                        "url_alias": "https://reliefweb.int/report/pk/test2",
                        "body-html": "<p>Major flood damage in Sindh province.</p>",
                        "country": [{"name": "Pakistan"}],
                        "language": [{"code": "en"}],
                        "date": {"original": "2026-03-04T00:00:00+00:00"},
                    }
                }
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if "api.reliefweb.int" in str(request.url):
                return httpx.Response(200, json=sample_payload)
            return httpx.Response(200, text="<html><body>Flood emergency update.</body></html>")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        connector = MockConnector(client=client)
        cfg = RuntimeConfig(countries=["Pakistan"], disaster_types=["flood"], check_interval_minutes=30)
        result = connector.fetch(config=cfg, limit=5, include_content=True)
        assert result.total_matched == 1
        item = result.items[0]
        assert item.title == "Fallback title"
        assert item.origin_url is None

    def test_api_query_includes_headline_and_origin_fields(self) -> None:
        """_build_query_payload includes 'headline' and 'origin' fields."""
        from agent_hum_crawler.config import RuntimeConfig
        from agent_hum_crawler.connectors.reliefweb import ReliefWebConnector

        connector = ReliefWebConnector(appname="test-app-x")
        cfg = RuntimeConfig(countries=["Pakistan"], disaster_types=["flood"], check_interval_minutes=30)
        payload = connector._build_query_payload(config=cfg, limit=20)
        fields_include = payload["fields"]["include"]
        assert "headline" in fields_include
        assert "origin" in fields_include

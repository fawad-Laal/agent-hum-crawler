import json

import httpx

from agent_hum_crawler.config import RuntimeConfig
from agent_hum_crawler.connectors.reliefweb import ReliefWebConnector


class MockedReliefWebConnector(ReliefWebConnector):
    def __init__(self, appname: str, client: httpx.Client):
        super().__init__(appname=appname)
        self._client = client

    def _build_client(self) -> httpx.Client:
        return self._client


def test_reliefweb_fetch_and_filter() -> None:
    sample_payload = {
        "data": [
            {
                "fields": {
                    "title": "Pakistan flood warning updated",
                    "url_alias": "https://reliefweb.int/report/pakistan/sample-1",
                    "body-html": "<p>Major flood impact in Sindh province.</p>",
                    "country": [{"name": "Pakistan"}],
                    "language": [{"code": "en"}],
                    "date": {"original": "2026-02-17T15:10:00+00:00"},
                    "file": [{"url": "https://reliefweb.int/report/sample.pdf"}],
                }
            },
            {
                "fields": {
                    "title": "Weather bulletin",
                    "url_alias": "https://reliefweb.int/report/other/sample-2",
                    "body-html": "<p>No matching disaster keyword here.</p>",
                    "country": [{"name": "Kenya"}],
                    "language": [{"code": "en"}],
                    "date": {"original": "2026-02-17T15:10:00+00:00"},
                }
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "api.reliefweb.int" in str(request.url):
            return httpx.Response(200, json=sample_payload)
        return httpx.Response(200, text="<html><body>Flood details and emergency update.</body></html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    connector = MockedReliefWebConnector(appname="approved-app", client=client)

    cfg = RuntimeConfig(
        countries=["Pakistan"],
        disaster_types=["flood"],
        check_interval_minutes=30,
    )

    result = connector.fetch(config=cfg, limit=5, include_content=True)

    assert result.total_fetched == 2
    assert result.total_matched == 1
    item = result.items[0]
    assert item.connector == "reliefweb"
    assert item.country_candidates == ["Pakistan"]
    assert item.content_mode == "content-level"
    assert any(src.type == "document_pdf" for src in item.content_sources)
    assert "flood" in item.text.lower()

    _ = json.dumps(result.model_dump(mode="json"))

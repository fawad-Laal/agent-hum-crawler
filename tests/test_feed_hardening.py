from types import SimpleNamespace

import httpx

from agent_hum_crawler.config import RuntimeConfig
from agent_hum_crawler.connectors.feed_base import FeedConnector, FeedSource


class FeedConnectorBase(FeedConnector):
    connector_name = "test"
    source_type = "news"


def test_bozo_recovery_path(monkeypatch):
    entries_obj = [SimpleNamespace(title="Pakistan flood alert", link="https://example.org/a", summary="flood in Pakistan")]

    def fake_parse(arg):
        if isinstance(arg, str):
            return SimpleNamespace(bozo=True, bozo_exception=Exception("bozo"), entries=[])
        return SimpleNamespace(bozo=False, entries=entries_obj)

    monkeypatch.setattr("agent_hum_crawler.connectors.feed_base.feedparser.parse", fake_parse)

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"<xml>placeholder</xml>")
    )

    class RecoveryConnector(FeedConnectorBase):
        def fetch(self, config, limit=20, include_content=True):
            return super().fetch(config, limit=limit, include_content=include_content)

    connector = RecoveryConnector(
        connector_name="test_connector",
        source_type="news",
        feeds=[FeedSource(name="Test Feed", url="https://example.org/feed.xml")],
    )

    original_client = httpx.Client

    def patched_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr("agent_hum_crawler.connectors.feed_base.httpx.Client", patched_client)

    cfg = RuntimeConfig(countries=["Pakistan"], disaster_types=["flood"], check_interval_minutes=30)
    result = connector.fetch(cfg, limit=1, include_content=False)

    assert result.total_fetched == 1
    assert result.total_matched == 1
    assert result.connector_metrics["healthy_sources"] == 1
    assert result.connector_metrics["failed_sources"] == 0
    assert result.connector_metrics["source_results"][0]["status"] == "recovered"

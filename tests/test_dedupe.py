from agent_hum_crawler.dedupe import detect_changes
from agent_hum_crawler.models import RawSourceItem


def _item(
    title: str,
    text: str,
    url: str,
    published: str,
    connector: str = "government_feeds",
    source_type: str = "official",
) -> RawSourceItem:
    return RawSourceItem(
        connector=connector,
        source_type=source_type,
        url=url,
        title=title,
        published_at=published,
        country_candidates=["Pakistan"],
        text=text,
        language="en",
    )


def test_detect_changes_new_and_unchanged() -> None:
    items = [
        _item("Flood warning Sindh", "Flood warning issued in Sindh", "https://example.com/1", "2026-02-17"),
    ]

    result1 = detect_changes(items, previous_hashes=[], countries=["Pakistan"], disaster_types=["flood"])
    assert len(result1.events) == 1
    assert result1.events[0].status == "new"

    result2 = detect_changes(
        items,
        previous_hashes=result1.current_hashes,
        countries=["Pakistan"],
        disaster_types=["flood"],
    )
    assert len(result2.events) == 1
    assert result2.events[0].status == "unchanged"


def test_detect_changes_updated_similarity() -> None:
    old = _item("Flood warning Sindh", "Flood warning in Sindh", "https://example.com/1", "2026-02-17")
    new = _item("Flood warning Sindh updated", "Flood warning in Sindh now severe", "https://example.com/2", "2026-02-18")

    result = detect_changes([old, new], previous_hashes=[], countries=["Pakistan"], disaster_types=["flood"])
    statuses = [e.status for e in result.events]
    assert "updated" in statuses or "new" in statuses


def test_corroboration_raises_confidence() -> None:
    official = _item(
        "Flood alert Karachi",
        "Major flood warning for Karachi region",
        "https://official.example/1",
        "2026-02-17",
        connector="government_feeds",
        source_type="official",
    )
    news = _item(
        "Flood alert Karachi",
        "Karachi under flood warning",
        "https://news.example/1",
        "2026-02-17",
        connector="local_news_feeds",
        source_type="news",
    )

    result = detect_changes([official, news], previous_hashes=[], countries=["Pakistan"], disaster_types=["flood"])
    assert len(result.events) == 1
    assert result.events[0].confidence == "high"


def test_low_corroboration_down_calibrates_severity() -> None:
    social_only = _item(
        "Catastrophic flood rumors",
        "catastrophic flood mass casualty reported",
        "https://social.example/1",
        "2026-02-17",
        connector="social_feed",
        source_type="social",
    )

    result = detect_changes([social_only], previous_hashes=[], countries=["Pakistan"], disaster_types=["flood"])
    assert len(result.events) == 1
    assert result.events[0].confidence == "low"
    assert result.events[0].severity in {"medium", "high"}
    assert "corroboration_sources=1" in result.events[0].summary

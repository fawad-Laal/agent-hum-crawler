import json
from pathlib import Path

from agent_hum_crawler.source_registry import load_registry


def test_load_registry_defaults_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no-file.json"
    registry = load_registry(["Pakistan"], path=missing)
    assert len(registry.government) >= 1
    assert len(registry.un) >= 1
    assert len(registry.ngo) >= 1


def test_load_registry_country_merge(tmp_path: Path) -> None:
    path = tmp_path / "country_sources.json"
    path.write_text(
        json.dumps(
            {
                "global": {
                    "local_news": [
                        {"name": "Global Local", "url": "https://example.com/global-local.xml"}
                    ]
                },
                "countries": {
                    "Pakistan": {
                        "local_news": [
                            {"name": "Pak Local", "url": "https://example.com/pak-local.xml"}
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    registry = load_registry(["Pakistan"], path=path)
    urls = {f.url for f in registry.local_news}
    assert "https://example.com/global-local.xml" in urls
    assert "https://example.com/pak-local.xml" in urls

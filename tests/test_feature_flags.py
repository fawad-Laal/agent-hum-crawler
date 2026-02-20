import json
from pathlib import Path

from agent_hum_crawler.feature_flags import load_feature_flags


def test_load_feature_flags_from_file(tmp_path: Path) -> None:
    path = tmp_path / "feature_flags.json"
    path.write_text(
        json.dumps(
            {
                "reliefweb_enabled": False,
                "llm_enrichment_enabled": True,
                "max_item_age_days_default": 14,
            }
        ),
        encoding="utf-8",
    )
    flags = load_feature_flags(path)
    assert flags["reliefweb_enabled"] is False
    assert flags["llm_enrichment_enabled"] is True
    assert int(flags["max_item_age_days_default"]) == 14


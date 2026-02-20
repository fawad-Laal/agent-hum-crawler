"""Dynamic gazetteer loader for admin-level geographic hierarchies.

Loads country gazetteers from:
  1. Local JSON files in ``config/gazetteers/<iso3>.json``
  2. LLM-generated fallback (cached after first generation)

Gazetteer JSON format::

    {
      "country": "Ethiopia",
      "iso3": "ETH",
      "admin1": {
        "Tigray": ["Central Tigray", "Eastern Tigray", ...],
        "Amhara": ["North Gondar", "South Gondar", ...],
        ...
      }
    }
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ── ISO3 lookup table ────────────────────────────────────────────────
# Covers all OCHA humanitarian-priority countries + common edge-cases.
# Add entries as needed — this is the canonical name→ISO3 map.

_COUNTRY_ISO3: dict[str, str] = {
    "afghanistan": "AFG",
    "bangladesh": "BGD",
    "burkina faso": "BFA",
    "burundi": "BDI",
    "cameroon": "CMR",
    "central african republic": "CAF",
    "chad": "TCD",
    "colombia": "COL",
    "democratic republic of the congo": "COD",
    "drc": "COD",
    "dr congo": "COD",
    "congo": "COG",
    "republic of the congo": "COG",
    "egypt": "EGY",
    "eritrea": "ERI",
    "ethiopia": "ETH",
    "haiti": "HTI",
    "india": "IND",
    "indonesia": "IDN",
    "iran": "IRN",
    "iraq": "IRQ",
    "kenya": "KEN",
    "lebanon": "LBN",
    "libya": "LBY",
    "madagascar": "MDG",
    "malawi": "MWI",
    "mali": "MLI",
    "mauritania": "MRT",
    "mozambique": "MOZ",
    "myanmar": "MMR",
    "nepal": "NPL",
    "niger": "NER",
    "nigeria": "NGA",
    "pakistan": "PAK",
    "palestine": "PSE",
    "philippines": "PHL",
    "rwanda": "RWA",
    "senegal": "SEN",
    "sierra leone": "SLE",
    "somalia": "SOM",
    "south sudan": "SSD",
    "sudan": "SDN",
    "syria": "SYR",
    "tanzania": "TZA",
    "turkey": "TUR",
    "turkiye": "TUR",
    "uganda": "UGA",
    "ukraine": "UKR",
    "venezuela": "VEN",
    "yemen": "YEM",
    "zambia": "ZMB",
    "zimbabwe": "ZWE",
}

# Reverse map: ISO3 → canonical country name
_ISO3_TO_NAME: dict[str, str] = {}
for _name, _code in _COUNTRY_ISO3.items():
    if _code not in _ISO3_TO_NAME:
        _ISO3_TO_NAME[_code] = _name


def country_to_iso3(country: str) -> str | None:
    """Return ISO3 code for a country name, or None if not found."""
    return _COUNTRY_ISO3.get(country.strip().lower())


def iso3_to_country(iso3: str) -> str | None:
    """Return canonical country name for an ISO3 code."""
    return _ISO3_TO_NAME.get(iso3.strip().upper())


def matches_country_safe(text: str, country: str) -> bool:
    """Word-boundary country match — prevents Niger/Nigeria cross-match."""
    term = " ".join(country.casefold().split())
    if not term:
        return False
    haystack = " ".join(text.casefold().split())
    pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
    return bool(re.search(pattern, haystack))


# ── Gazetteer cache ──────────────────────────────────────────────────

_GAZETTEER_DIR = Path(__file__).resolve().parents[2] / "config" / "gazetteers"
_cache: dict[str, dict[str, list[str]]] = {}
_cache_lock = threading.Lock()


def _gazetteer_path(iso3: str) -> Path:
    """Return path for a country's gazetteer JSON file."""
    return _GAZETTEER_DIR / f"{iso3.lower()}.json"


def _load_from_file(iso3: str) -> dict[str, list[str]] | None:
    """Load gazetteer from JSON file if it exists."""
    path = _gazetteer_path(iso3)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        admin1 = data.get("admin1", {})
        if isinstance(admin1, dict):
            _log.info("Gazetteer loaded from file: %s (%d admin1 areas)", path.name, len(admin1))
            return admin1
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        _log.warning("Invalid gazetteer file %s: %s", path, exc)
    return None


def _save_to_file(iso3: str, country: str, admin1: dict[str, list[str]]) -> None:
    """Persist a gazetteer to disk for future use."""
    _GAZETTEER_DIR.mkdir(parents=True, exist_ok=True)
    path = _gazetteer_path(iso3)
    data = {"country": country.title(), "iso3": iso3.upper(), "admin1": admin1}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _log.info("Gazetteer saved: %s (%d admin1 areas)", path.name, len(admin1))


def _generate_via_llm(country: str, iso3: str) -> dict[str, list[str]] | None:
    """Generate a gazetteer using LLM with strict JSON schema.

    Returns admin1 → [admin2] dict or None on failure.
    """
    try:
        import httpx
        from .settings import get_openai_api_key, get_openai_model
    except ImportError:
        _log.warning("Cannot generate gazetteer: missing dependencies")
        return None

    api_key = get_openai_api_key()
    if not api_key:
        _log.warning("Cannot generate gazetteer: no OPENAI_API_KEY")
        return None

    model = os.environ.get("OPENAI_MODEL_GAZETTEER", get_openai_model())

    schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["country", "iso3", "admin1"],
        "properties": {
            "country": {"type": "string"},
            "iso3": {"type": "string"},
            "admin1": {
                "type": "object",
                "description": "Map of admin1 (region/state/province) names to arrays of admin2 (district/zone/woreda) names",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
    }

    system_prompt = (
        "You are a geographic reference data generator for humanitarian operations. "
        "Return the official administrative divisions for the requested country. "
        "Use the most commonly used English names for each administrative area. "
        "admin1 = first-level divisions (regions, states, provinces). "
        "admin2 = second-level divisions (districts, zones, woredas, counties). "
        "Include ALL admin1 areas. For admin2, include the most significant ones "
        "(major cities, crisis-affected areas, humanitarian hubs). "
        "Use names as they appear in OCHA/UN documents when possible."
    )

    user_prompt = (
        f"Generate the administrative boundary gazetteer for {country.title()} (ISO3: {iso3.upper()}). "
        f"Include all admin1 regions and their key admin2 subdivisions."
    )

    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "input": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "country_gazetteer",
                            "schema": schema,
                            "strict": True,
                        }
                    },
                },
            )
            resp.raise_for_status()
            body = resp.json()

        # Extract text from Responses API output
        text_content = ""
        for item in body.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        text_content = part.get("text", "")
                        break

        if not text_content:
            _log.warning("LLM gazetteer generation returned empty response for %s", country)
            return None

        parsed = json.loads(text_content)
        admin1 = parsed.get("admin1", {})
        if not isinstance(admin1, dict) or not admin1:
            _log.warning("LLM gazetteer has no admin1 data for %s", country)
            return None

        _log.info("LLM-generated gazetteer for %s: %d admin1 areas", country, len(admin1))
        return admin1

    except Exception as exc:
        _log.warning("LLM gazetteer generation failed for %s: %s", country, exc)
        return None


# ── Public API ───────────────────────────────────────────────────────

def get_gazetteer(country: str) -> dict[str, list[str]] | None:
    """Get admin hierarchy for a country.

    Resolution order:
      1. In-memory cache
      2. Local JSON file (``config/gazetteers/<iso3>.json``)
      3. LLM generation (result cached to file)
      4. Legacy hardcoded gazetteers (fallback)

    Returns admin1 → [admin2] dict, or None if unavailable.
    """
    key = country.strip().lower()
    iso3 = country_to_iso3(key)

    with _cache_lock:
        if key in _cache:
            return _cache[key]

    # Try loading from file
    admin1 = None
    if iso3:
        admin1 = _load_from_file(iso3)

    # Try LLM generation
    if admin1 is None and iso3:
        admin1 = _generate_via_llm(country, iso3)
        if admin1:
            _save_to_file(iso3, country, admin1)

    # Try legacy hardcoded gazetteers as final fallback
    if admin1 is None:
        from .graph_ontology import COUNTRY_GAZETTEERS
        admin1 = COUNTRY_GAZETTEERS.get(key)
        if admin1:
            _log.info("Using legacy hardcoded gazetteer for %s", country)

    if admin1:
        with _cache_lock:
            _cache[key] = admin1
        return admin1

    _log.info("No gazetteer available for %s (iso3=%s)", country, iso3)
    return None


def build_admin_hierarchy(countries: list[str]) -> dict[str, list[str]]:
    """Build merged admin hierarchy for a list of countries.

    Replaces ``build_auto_admin_hierarchy`` from graph_ontology.py
    with dynamic loading support.
    """
    merged: dict[str, list[str]] = {}
    for c in countries:
        gaz = get_gazetteer(c)
        if gaz:
            for admin1, districts in gaz.items():
                merged[admin1] = districts
    return merged


def preload_gazetteers(countries: list[str]) -> dict[str, int]:
    """Preload gazetteers for a list of countries. Returns load status."""
    status: dict[str, int] = {}
    for c in countries:
        gaz = get_gazetteer(c)
        status[c] = len(gaz) if gaz else 0
    return status


def list_cached_countries() -> list[str]:
    """Return list of countries with cached gazetteers."""
    with _cache_lock:
        return list(_cache.keys())


def list_available_files() -> list[str]:
    """Return list of ISO3 codes with gazetteer files on disk."""
    if not _GAZETTEER_DIR.exists():
        return []
    return [f.stem.upper() for f in _GAZETTEER_DIR.glob("*.json")]

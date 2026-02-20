"""URL canonicalization helpers for citation quality."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "oc",
    "ved",
    "cid",
}


def _strip_tracking_params(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=False)
    clean_qs: dict[str, list[str]] = {}
    for key, values in qs.items():
        lk = key.lower()
        if lk in TRACKING_QUERY_KEYS:
            continue
        if any(lk.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        clean_qs[key] = values
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(clean_qs, doseq=True),
            "",
        )
    )


def _extract_google_target(url: str) -> str | None:
    parsed = urlparse(url)
    if "news.google." not in parsed.netloc.lower():
        return None
    qs = parse_qs(parsed.query, keep_blank_values=False)
    for key in ("url", "u", "q"):
        values = qs.get(key, [])
        if values:
            candidate = values[0].strip()
            if candidate.startswith("http://") or candidate.startswith("https://"):
                return candidate
    return None


def canonicalize_url(url: str, client: httpx.Client | None = None) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw

    hinted = _extract_google_target(raw)
    if hinted:
        return _strip_tracking_params(hinted)

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    if "news.google." in host and "/rss/articles/" in parsed.path:
        if client is not None:
            try:
                resp = client.get(
                    raw,
                    follow_redirects=True,
                    timeout=10.0,
                    headers={"User-Agent": "AHC-Canonicalizer/1.0"},
                )
                final_url = str(resp.url)
                if final_url:
                    return _strip_tracking_params(final_url)
            except Exception:
                pass
    return _strip_tracking_params(raw)

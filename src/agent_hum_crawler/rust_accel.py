"""Rust-accelerated functions with transparent Python fallback.

If the ``moltis_rust_core`` native extension is available (built via
``maturin develop``), hot-path functions execute in compiled Rust.
Otherwise the original pure-Python implementations are used, keeping
the project fully functional without a Rust toolchain.

Usage
-----
>>> from agent_hum_crawler.rust_accel import extract_figures, similarity_ratio
>>> extract_figures("death toll rises to 59")
{'deaths': 59}
>>> similarity_ratio("cyclone hits coast", "cyclone strikes coast")
0.82...
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# ── Try to load the Rust extension ───────────────────────────────────

_RUST_AVAILABLE = False

try:
    import moltis_rust_core as _rc  # type: ignore[import-untyped]

    _RUST_AVAILABLE = True
    _log.info("Rust acceleration enabled (moltis_rust_core loaded)")
except ImportError:
    _rc = None  # type: ignore[assignment]
    _log.info("Rust acceleration unavailable — using pure-Python fallback")


def rust_available() -> bool:
    """Return True if the native Rust module is loaded."""
    return _RUST_AVAILABLE


# ── Figure extraction ────────────────────────────────────────────────

def extract_figures(text: str) -> dict[str, int]:
    """Extract humanitarian figures from text.

    Returns a dict mapping figure keys (deaths, displaced, etc.)
    to integer values.
    """
    if _RUST_AVAILABLE:
        return dict(_rc.extract_figures(text))

    # Python fallback — lazy import to avoid circular deps
    from .graph_ontology import _extract_figures
    return _extract_figures(text)


# ── Text classification ──────────────────────────────────────────────

def classify_impact_type(text: str) -> str:
    """Classify the dominant impact type from text.

    Returns the string value of the ImpactType enum.
    """
    if _RUST_AVAILABLE:
        return _rc.classify_impact_type(text)

    from .graph_ontology import _classify_impact_type
    return _classify_impact_type(text).value


def classify_need_types(text: str) -> list[str]:
    """Find all need types mentioned in text.

    Returns a list of NeedType string values.
    """
    if _RUST_AVAILABLE:
        return list(_rc.classify_need_types(text))

    from .graph_ontology import _classify_need_types
    return [n.value for n in _classify_need_types(text)]


def severity_from_text(text: str) -> int:
    """Estimate IPC-like severity phase (1-5) from text keywords."""
    if _RUST_AVAILABLE:
        return _rc.severity_from_text(text)

    from .graph_ontology import _severity_from_text
    return _severity_from_text(text)


def is_risk_text(text: str) -> bool:
    """Check whether text contains risk or forecast language."""
    if _RUST_AVAILABLE:
        return _rc.is_risk_text(text)

    from .graph_ontology import _is_risk_text
    return _is_risk_text(text)


def detect_response_actor(text: str) -> tuple[str, str] | None:
    """Detect a response actor from text.

    Returns ``(actor_name, actor_type)`` or ``None``.
    """
    if _RUST_AVAILABLE:
        result = _rc.detect_response_actor(text)
        return tuple(result) if result else None  # type: ignore[return-value]

    from .graph_ontology import _detect_response_actor
    return _detect_response_actor(text)


def detect_admin_area(
    text: str,
    area_names: list[tuple[str, int]],
) -> tuple[str, int] | None:
    """Detect an admin area name in text.

    Parameters
    ----------
    text : str
        Evidence text to scan.
    area_names : list[tuple[str, int]]
        (area_name, admin_level) pairs from the gazetteer.

    Returns
    -------
    tuple[str, int] | None
        ``(matched_name, admin_level)`` or ``None``.
    """
    if _RUST_AVAILABLE:
        result = _rc.detect_admin_area(text, area_names)
        return tuple(result) if result else None  # type: ignore[return-value]

    from .graph_ontology import _detect_admin_area
    return _detect_admin_area(text, area_names)


# ── Fuzzy deduplication ──────────────────────────────────────────────

def similarity_ratio(a: str, b: str) -> float:
    """String similarity ratio (0.0–1.0) via LCS."""
    if _RUST_AVAILABLE:
        return _rc.similarity_ratio(a, b)

    from difflib import SequenceMatcher
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_text(text: str) -> str:
    """Case-fold and collapse whitespace."""
    if _RUST_AVAILABLE:
        return _rc.normalize_text(text)

    return " ".join(text.lower().split())


def cluster_titles(titles: list[str], threshold: float = 0.90) -> list[list[int]]:
    """Group title indices by fuzzy similarity.

    Returns a list of clusters, where each cluster is a list of
    indices into the original ``titles`` list.
    """
    if _RUST_AVAILABLE:
        return [list(c) for c in _rc.cluster_titles(titles, threshold)]

    # Python fallback
    normed = [normalize_text(t) for t in titles]
    clusters: list[list[int]] = []
    for i, title in enumerate(normed):
        placed = False
        for cluster in clusters:
            pivot = normed[cluster[0]]
            if similarity_ratio(title, pivot) >= threshold:
                cluster.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
    return clusters


# ── URL canonicalization ─────────────────────────────────────────────

def canonicalize_url(url: str) -> str:
    """Canonicalize a URL: strip tracking params, fragments, etc."""
    if _RUST_AVAILABLE:
        return _rc.canonicalize_url(url)

    from .url_canonical import canonicalize_url as _py_canon
    return _py_canon(url)


def strip_tracking_params(url: str) -> str:
    """Remove common tracking query parameters."""
    if _RUST_AVAILABLE:
        return _rc.strip_tracking_params(url)

    from .url_canonical import _strip_tracking_params as _py_strip
    return _py_strip(url)

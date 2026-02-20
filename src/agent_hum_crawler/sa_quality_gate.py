"""Situation Analysis quality gate.

Provides automated quality scoring for OCHA-style Situation Analysis
reports.  The gate checks completeness, citation quality, data
density, and structural compliance before a report is released.

Quality dimensions
------------------
1. **Section completeness** — are all expected sections present?
2. **Key figure coverage** — percentage of national figures populated
3. **Citation density** — average citations per narrative section
4. **Citation accuracy** — fraction of valid ``[N]`` references
5. **Admin coverage** — does the report include admin1/admin2 data?
6. **Date attribution** — do key figures carry "as of" dates?

The ``score_situation_analysis()`` function returns a detailed dict
and a boolean pass/fail verdict.  A caller may then decide whether to
publish, flag for human review, or reject the SA.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

# ── Thresholds (configurable via override dicts) ─────────────────────

_DEFAULT_THRESHOLDS: dict[str, float] = {
    # Minimum fraction of expected sections that must be non-empty
    "section_completeness_min": 0.70,
    # Minimum fraction of national key figures that should be > 0
    "key_figure_coverage_min": 0.30,
    # Minimum citation accuracy (valid / total refs)
    "citation_accuracy_min": 0.80,
    # Minimum average citations per narrative section
    "citation_density_min": 0.5,
    # Minimum fraction of admin1 areas with data
    "admin_coverage_min": 0.20,
    # Minimum fraction of dated key figures (with "as of" date)
    "date_attribution_min": 0.30,
    # Overall weighted score threshold (0.0–1.0) for pass
    "overall_pass_threshold": 0.55,
}

# Weights for computing overall score
_DIMENSION_WEIGHTS: dict[str, float] = {
    "section_completeness": 0.25,
    "key_figure_coverage": 0.20,
    "citation_accuracy": 0.15,
    "citation_density": 0.10,
    "admin_coverage": 0.15,
    "date_attribution": 0.15,
}

# ── Expected sections in an OCHA SA ─────────────────────────────────

_EXPECTED_SECTIONS = [
    "Executive Summary",
    "National Impact Overview",
    "Province-Level",
    "District-Level",
    "Shelter",
    "WASH",
    "Health",
    "Food Security",
    "Protection",
    "Education",
    "Access Constraints",
    "Outstanding Needs",
    "Forecast",
    "Annex",
    "Sources and References",
]

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+)", re.MULTILINE)

_CITATION_REF_RE = re.compile(r"\[(\d+)\]")

# Key figure labels we expect to find in the national impact table
_KEY_FIGURE_LABELS = [
    "affected",
    "displaced",
    "deaths",
    "injured",
    "missing",
    "houses_damaged",
    "houses_destroyed",
]

_KEY_FIGURE_TABLE_RE = re.compile(
    r"\|\s*\*{0,2}(\w[\w\s]*?)\*{0,2}\s*\|\s*([\d,]+)\s*",
    re.MULTILINE,
)

_AS_OF_RE = re.compile(r"as of \d{4}", re.IGNORECASE)


# ── Public API ───────────────────────────────────────────────────────

@dataclass
class SAQualityResult:
    """Quality gate result for a Situation Analysis."""

    # Per-dimension scores (0.0–1.0)
    section_completeness: float = 0.0
    key_figure_coverage: float = 0.0
    citation_accuracy: float = 0.0
    citation_density: float = 0.0
    admin_coverage: float = 0.0
    date_attribution: float = 0.0

    # Overall weighted score
    overall_score: float = 0.0

    # Pass / fail
    passed: bool = False

    # Per-dimension detail
    details: dict[str, Any] = field(default_factory=dict)

    # Thresholds used
    thresholds: dict[str, float] = field(default_factory=dict)


def score_situation_analysis(
    markdown: str,
    *,
    citation_numbers: dict[str, int] | None = None,
    thresholds: dict[str, float] | None = None,
) -> SAQualityResult:
    """Score a rendered SA markdown against quality dimensions.

    Parameters
    ----------
    markdown:
        Full markdown text of the rendered Situation Analysis.
    citation_numbers:
        URL → citation-number mapping (from ``build_citation_numbers``).
        Used for citation accuracy checking.  If ``None`` the gate
        parses the Citations section for the valid set.
    thresholds:
        Override any of the default threshold values.

    Returns
    -------
    SAQualityResult with per-dimension scores and pass/fail.
    """
    effective_thresholds = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}
    result = SAQualityResult(thresholds=effective_thresholds)

    # 1. Section completeness
    headings = _SECTION_HEADING_RE.findall(markdown)
    present_count = 0
    missing_sections: list[str] = []
    for expected in _EXPECTED_SECTIONS:
        found = any(expected.lower() in h.lower() for h in headings)
        if found:
            present_count += 1
        else:
            missing_sections.append(expected)
    result.section_completeness = present_count / len(_EXPECTED_SECTIONS) if _EXPECTED_SECTIONS else 0.0
    result.details["section_completeness"] = {
        "expected": len(_EXPECTED_SECTIONS),
        "present": present_count,
        "missing": missing_sections,
    }

    # 2. Key figure coverage
    figure_hits = _KEY_FIGURE_TABLE_RE.findall(markdown)
    populated_figures = 0
    total_figures = len(_KEY_FIGURE_LABELS)
    found_labels: list[str] = []
    for label_raw, value in figure_hits:
        label_clean = label_raw.strip().lower().replace(" ", "_")
        if label_clean in _KEY_FIGURE_LABELS:
            val = value.replace(",", "").strip()
            if val.isdigit() and int(val) > 0:
                populated_figures += 1
                found_labels.append(label_clean)
    result.key_figure_coverage = populated_figures / total_figures if total_figures else 0.0
    result.details["key_figure_coverage"] = {
        "total_expected": total_figures,
        "populated": populated_figures,
        "found_labels": found_labels,
    }

    # 3. Citation accuracy
    valid_numbers = set()
    if citation_numbers:
        valid_numbers = set(citation_numbers.values())
    else:
        # Parse citations section
        cit_section = _extract_section(markdown, "Sources and References")
        for line in cit_section.splitlines():
            line = line.strip()
            if line and line[0].isdigit():
                try:
                    num = int(line.split(".")[0])
                    valid_numbers.add(num)
                except ValueError:
                    pass

    all_refs = _CITATION_REF_RE.findall(markdown)
    total_refs = len(all_refs)
    valid_refs = sum(1 for r in all_refs if int(r) in valid_numbers) if valid_numbers else total_refs
    invalid_refs = total_refs - valid_refs
    result.citation_accuracy = valid_refs / total_refs if total_refs else 1.0
    result.details["citation_accuracy"] = {
        "total_refs": total_refs,
        "valid_refs": valid_refs,
        "invalid_refs": invalid_refs,
        "known_citation_numbers": len(valid_numbers),
    }

    # 4. Citation density (citations per narrative section)
    narrative_sections = _count_narrative_sections(markdown)
    raw_density = total_refs / narrative_sections if narrative_sections else 0.0
    result.citation_density = min(1.0, raw_density)  # cap at 1.0
    result.details["citation_density"] = {
        "total_refs": total_refs,
        "narrative_sections": narrative_sections,
        "avg_per_section": round(raw_density, 2),
    }

    # 5. Admin coverage
    admin1_rows = len(re.findall(
        r"^\|[^|]+\|[^|]+\|[^|]+\|",
        markdown,
        re.MULTILINE,
    ))
    # Rough heuristic: at least some table rows with admin data
    admin1_section = _extract_section(markdown, "Province-Level")
    admin_data_rows = [
        line for line in admin1_section.splitlines()
        if line.strip().startswith("|") and "---" not in line and "Field" not in line
    ]
    # Exclude header rows
    admin_data_rows = [r for r in admin_data_rows if not re.match(r"^\|\s*#\s*\|", r)]
    total_admin_rows = len(admin_data_rows)
    result.admin_coverage = min(1.0, total_admin_rows / 5) if total_admin_rows > 0 else 0.0
    result.details["admin_coverage"] = {
        "admin1_data_rows": total_admin_rows,
    }

    # 6. Date attribution
    figure_section = _extract_section(markdown, "National Impact")
    date_refs = _AS_OF_RE.findall(figure_section)
    dated_figures = len(date_refs)
    result.date_attribution = min(1.0, dated_figures / max(1, populated_figures)) if populated_figures else 0.0
    result.details["date_attribution"] = {
        "dated_figures": dated_figures,
        "populated_figures": populated_figures,
    }

    # Overall weighted score
    overall = 0.0
    for dim, weight in _DIMENSION_WEIGHTS.items():
        val = getattr(result, dim, 0.0)
        overall += weight * val
    result.overall_score = round(overall, 3)
    result.passed = result.overall_score >= effective_thresholds["overall_pass_threshold"]

    # Per-dimension pass/fail
    dim_verdicts: dict[str, bool] = {}
    for dim in _DIMENSION_WEIGHTS:
        threshold_key = f"{dim}_min"
        threshold_val = effective_thresholds.get(threshold_key, 0.0)
        dim_verdicts[dim] = getattr(result, dim, 0.0) >= threshold_val
    result.details["dimension_verdicts"] = dim_verdicts

    _log.info(
        "SA quality gate: overall=%.3f passed=%s (threshold=%.2f)",
        result.overall_score,
        result.passed,
        effective_thresholds["overall_pass_threshold"],
    )

    return result


def quality_summary_markdown(result: SAQualityResult) -> str:
    """Render a short markdown summary of SA quality scores.

    Appended to the SA footer when the quality gate is enabled.
    """
    verdict = "PASS" if result.passed else "FAIL"
    lines = [
        "",
        "---",
        "",
        f"### Quality Gate: **{verdict}** (score {result.overall_score:.2f})",
        "",
        "| Dimension | Score | Threshold | Status |",
        "|-----------|-------|-----------|--------|",
    ]
    for dim, weight in _DIMENSION_WEIGHTS.items():
        score_val = getattr(result, dim, 0.0)
        threshold_key = f"{dim}_min"
        threshold_val = result.thresholds.get(threshold_key, 0.0)
        status = "Pass" if score_val >= threshold_val else "**Fail**"
        label = dim.replace("_", " ").title()
        lines.append(
            f"| {label} | {score_val:.2f} | {threshold_val:.2f} | {status} |"
        )
    lines.append("")
    return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────

def _extract_section(markdown: str, heading_fragment: str) -> str:
    """Extract text between a heading containing *heading_fragment* and the next ``##``."""
    pattern = re.compile(
        rf"^##\s+[^\n]*{re.escape(heading_fragment)}[^\n]*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(markdown)
    return m.group(1) if m else ""


def _count_narrative_sections(markdown: str) -> int:
    """Count sections that likely have prose text (not just tables)."""
    count = 0
    sections = re.split(r"^##\s+", markdown, flags=re.MULTILINE)
    for section in sections[1:]:  # skip pre-header text
        lines = section.strip().splitlines()
        prose_lines = [
            l for l in lines[1:]  # skip heading line
            if l.strip()
            and not l.strip().startswith("|")
            and not l.strip().startswith("---")
            and not l.strip().startswith("#")
        ]
        if len(prose_lines) >= 2:
            count += 1
    return max(count, 1)

"""NLP drift-guard — Rust must produce identical output to Python for fixed sentences.

For each of the five NLP functions exposed by ``rust_accel``, we run 20
canonical sentences and assert that the Rust-path result exactly matches the
pure-Python implementation in ``graph_ontology``.

These tests protect against silent keyword-table drift between the two
implementations.  They run automatically when the Rust extension is built
(``maturin develop``).  If the extension is absent, the entire module is
skipped — it is never expected to break the CI of developers without a
Rust toolchain.

Run:
    cd rust_core && maturin develop   # build once
    pytest tests/test_nlp_drift_guard.py -v
"""

from __future__ import annotations

import pytest

# Skip everything if the Rust extension is not compiled.
pytest.importorskip("moltis_rust_core", reason="moltis_rust_core not built — run: cd rust_core && maturin develop")

# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rust_mod():
    """The compiled Rust extension."""
    import moltis_rust_core as rc  # noqa: PLC0415
    return rc


@pytest.fixture(scope="module")
def py_ontology():
    """Graph ontology module for pure-Python reference."""
    from agent_hum_crawler import graph_ontology as go  # noqa: PLC0415
    return go


# ── Sentence corpora ──────────────────────────────────────────────────

IMPACT_SENTENCES: list[tuple[str, str]] = [
    # (sentence, expected_dominant_label)
    ("At least 52 people killed and 100 injured in the flooding",         "people_impact"),
    ("Death toll rises to 87 after the earthquake",                       "people_impact"),
    ("More than 16,000 people were displaced following the cyclone",       "people_impact"),
    ("Three bridges collapsed and roads are blocked",                      "infrastructure_impact"),
    ("Power grid is down in the affected districts",                      "infrastructure_impact"),
    ("Two hospitals damaged and four clinics are non-functional",          "services_impact"),
    ("School buildings destroyed across 12 districts",                    "services_impact"),
    ("Hundreds of houses destroyed and shelter is needed",                "housing_lc_impact"),
    ("Homes damaged in coastal areas; housing stock depleted",            "housing_lc_impact"),
    ("Agricultural livelihoods shattered; markets have collapsed",        "systems_impact"),
]

ALL_IMPACT_SENTENCES: list[tuple[str, list[str]]] = [
    # (sentence, expected labels that MUST be present — order-insensitive subset)
    ("52 killed and 3 bridges collapsed",                    ["people_impact", "infrastructure_impact"]),
    ("School damaged, hospital offline, 12 dead",            ["people_impact", "services_impact"]),
    ("Houses destroyed, many families displaced",            ["housing_lc_impact", "people_impact"]),
    ("No relevant keywords here",                            ["people_impact"]),  # fallback
]

NEED_SENTENCES: list[tuple[str, list[str]]] = [
    # (sentence, expected need labels that must appear)
    ("Food insecurity is rising and water contamination is severe",     ["food_security", "wash"]),
    ("Cholera outbreak requires immediate medical response",            ["health"]),
    ("Children need shelter and protection services urgently",         ["shelter", "protection"]),
    ("Schools are damaged: education response is critical",            ["education"]),
    ("Logistics access is hampered due to road damage",                ["logistics"]),
]

SEVERITY_SENTENCES: list[tuple[str, int]] = [
    ("This is a catastrophic famine situation",              5),
    ("A state of emergency has been declared",               4),
    ("Major damage reported across the region",              3),
    ("The situation is moderately stressed",                 2),
    ("Routine update from the field team",                   1),
]

RISK_SENTENCES: list[tuple[str, bool]] = [
    ("Forecast shows heavy rainfall next week",              True),
    ("Risk of another cyclone is anticipated",               True),
    ("Outlook remains concerning for the coming months",     True),
    ("The damage has already been recorded",                 False),
    ("Response teams are deployed in the area",              False),
]

FIGURE_SENTENCES: list[tuple[str, list[str]]] = [
    # (sentence, figure keys that MUST appear in both Rust and Python output)
    ("52 deaths confirmed",                                  ["deaths"]),
    ("Death toll rises to 87",                               ["deaths"]),
    ("16,000 people displaced by the flood",                 ["people_affected"]),
    ("45 people injured in the collapse",                    ["people_affected"]),
    ("No figures in this sentence",                          []),
]


# ── Tests: classify_impact_type (dominant label) ──────────────────────

@pytest.mark.parametrize("text,expected_label", IMPACT_SENTENCES)
def test_classify_impact_type_rust_matches_python(text, expected_label, rust_mod, py_ontology):
    rust_result = rust_mod.classify_impact_type(text)
    py_result = py_ontology._classify_impact_type(text).value
    # Both should agree with each other (and ideally with expected_label)
    assert rust_result == py_result, (
        f"Rust/Python mismatch for: {text!r}\n"
        f"  Rust  => {rust_result!r}\n"
        f"  Python=> {py_result!r}"
    )


# ── Tests: classify_all_impact_types (multi-label) ────────────────────

@pytest.mark.parametrize("text,must_include", ALL_IMPACT_SENTENCES)
def test_classify_all_impact_types_rust_matches_python(text, must_include, rust_mod, py_ontology):
    rust_result = list(rust_mod.classify_all_impact_types(text))
    py_result = [t.value for t in py_ontology._classify_all_impact_types(text)]

    # Both return sets must be equal (order can differ)
    assert set(rust_result) == set(py_result), (
        f"Rust/Python set mismatch for: {text!r}\n"
        f"  Rust  => {rust_result!r}\n"
        f"  Python=> {py_result!r}"
    )
    # Must include all required labels
    for label in must_include:
        assert label in rust_result, (
            f"Expected {label!r} in Rust result for: {text!r}\n"
            f"  Got: {rust_result!r}"
        )


# ── Tests: classify_need_types ────────────────────────────────────────

@pytest.mark.parametrize("text,must_include", NEED_SENTENCES)
def test_classify_need_types_rust_matches_python(text, must_include, rust_mod, py_ontology):
    rust_result = list(rust_mod.classify_need_types(text))
    py_result = [n.value for n in py_ontology._classify_need_types(text)]

    assert set(rust_result) == set(py_result), (
        f"Rust/Python set mismatch for: {text!r}\n"
        f"  Rust  => {rust_result!r}\n"
        f"  Python=> {py_result!r}"
    )
    for label in must_include:
        assert label in rust_result, (
            f"Expected {label!r} in Rust result for: {text!r}\n"
            f"  Got: {rust_result!r}"
        )


# ── Tests: severity_from_text ─────────────────────────────────────────

@pytest.mark.parametrize("text,expected_phase", SEVERITY_SENTENCES)
def test_severity_from_text_rust_matches_python(text, expected_phase, rust_mod, py_ontology):
    rust_result = rust_mod.severity_from_text(text)
    py_result = py_ontology._severity_from_text(text)
    assert rust_result == py_result, (
        f"Rust/Python severity mismatch for: {text!r}\n"
        f"  Rust  => {rust_result}\n"
        f"  Python=> {py_result}"
    )
    assert rust_result == expected_phase, (
        f"Wrong severity for: {text!r}  expected={expected_phase}  got={rust_result}"
    )


# ── Tests: is_risk_text ───────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", RISK_SENTENCES)
def test_is_risk_text_rust_matches_python(text, expected, rust_mod, py_ontology):
    rust_result = rust_mod.is_risk_text(text)
    py_result = py_ontology._is_risk_text(text)
    assert rust_result == py_result, (
        f"Rust/Python risk mismatch for: {text!r}\n"
        f"  Rust  => {rust_result}\n"
        f"  Python=> {py_result}"
    )
    assert rust_result == expected


# ── Tests: extract_figures ────────────────────────────────────────────

@pytest.mark.parametrize("text,must_have_keys", FIGURE_SENTENCES)
def test_extract_figures_rust_matches_python(text, must_have_keys, rust_mod, py_ontology):
    rust_result = dict(rust_mod.extract_figures(text))
    py_result = py_ontology._extract_figures(text)
    assert rust_result == py_result, (
        f"Rust/Python figure mismatch for: {text!r}\n"
        f"  Rust  => {rust_result}\n"
        f"  Python=> {py_result}"
    )
    for key in must_have_keys:
        assert key in rust_result, (
            f"Expected figure key {key!r} for: {text!r}  got={rust_result}"
        )

//! Text classification — keyword matching for humanitarian impacts, needs, severity.
//!
//! Keyword tables are generated at compile time from `config/nlp_keywords.toml`
//! by `build.rs`; this file includes the generated constants via `include!`.
//! This ensures Rust and Python always share the same keyword definitions.

use pyo3::prelude::*;
use pyo3::types::PyList;
use regex::Regex;

// ── Generated keyword data (from config/nlp_keywords.toml via build.rs) ─────
//
//   IMPACT_KEYWORD_DATA : &[(&str, &[&str])]  — (label, keywords) pairs
//   NEED_KEYWORD_DATA   : &[(&str, &[&str])]  — (label, keywords) pairs
//   RISK_KEYWORD_DATA   : &[&str]             — flat keyword list
//
include!(concat!(env!("OUT_DIR"), "/keywords.rs"));

static RESPONSE_ACTORS: &[(&str, &str)] = &[
    ("un", "un_agency"),
    ("ocha", "un_agency"),
    ("unicef", "un_agency"),
    ("wfp", "un_agency"),
    ("who", "un_agency"),
    ("unhcr", "un_agency"),
    ("ifrc", "redco"),
    ("red cross", "redco"),
    ("red crescent", "redco"),
    ("government", "government"),
    ("ministry", "government"),
    ("national disaster", "government"),
    ("ingd", "government"),
    ("cenoe", "government"),
    ("ngo", "ngo"),
    ("care", "ngo"),
    ("oxfam", "ngo"),
    ("msf", "ngo"),
    ("save the children", "ngo"),
    ("cluster", "cluster"),
];

// ── Word-boundary regex builder ─────────────────────────────────────

fn contains_keyword(haystack: &str, keyword: &str) -> bool {
    // Multi-word phrases: simple substring (already specific enough)
    if keyword.contains(' ') {
        return haystack.contains(keyword);
    }
    // Single-word: require a word-START boundary so "road" doesn't match
    // "railroad", but allow any suffix so "bridge" matches "bridges".
    if let Some(pos) = haystack.find(keyword) {
        pos == 0 || !haystack.as_bytes()[pos - 1].is_ascii_alphanumeric()
    } else {
        false
    }
}

/// Classify the *dominant* impact type from text (single-label).
///
/// Returns one of: `"people_impact"`, `"housing_lc_impact"`,
/// `"infrastructure_impact"`, `"services_impact"`, `"systems_impact"`.
#[pyfunction]
pub fn classify_impact_type(text: &str) -> String {
    let haystack = text.to_lowercase();
    let mut best_label = "people_impact";
    let mut best_score = 0i32;

    for &(label, keywords) in IMPACT_KEYWORD_DATA {
        let score = keywords
            .iter()
            .filter(|&&kw| contains_keyword(&haystack, kw))
            .count() as i32;
        if score > best_score {
            best_score = score;
            best_label = label;
        }
    }
    best_label.to_string()
}

/// Find **all** impact types with keyword matches, ordered by score (multi-label).
///
/// A single Flash Update may mention deaths (people), destroyed bridges
/// (infrastructure), and damaged clinics (services).  This function returns all
/// matching types so callers can create one `ImpactObservation` per type.
/// Falls back to `["people_impact"]` when nothing matches.
#[pyfunction]
pub fn classify_all_impact_types(py: Python<'_>, text: &str) -> PyResult<Py<PyList>> {
    let haystack = text.to_lowercase();
    let mut scored: Vec<(&str, i32)> = Vec::new();

    for &(label, keywords) in IMPACT_KEYWORD_DATA {
        let score = keywords
            .iter()
            .filter(|&&kw| contains_keyword(&haystack, kw))
            .count() as i32;
        if score > 0 {
            scored.push((label, score));
        }
    }

    if scored.is_empty() {
        let list = PyList::new_bound(py, &["people_impact"]);
        return Ok(list.unbind());
    }

    // Descending by score; stable insertion order for ties
    scored.sort_by(|a, b| b.1.cmp(&a.1));
    let labels: Vec<&str> = scored.iter().map(|(label, _)| *label).collect();
    let list = PyList::new_bound(py, labels);
    Ok(list.unbind())
}

/// Find all need types mentioned in text (multi-label).
///
/// Returns a list of need type strings, e.g. `["food_security", "wash"]`.
#[pyfunction]
pub fn classify_need_types(py: Python<'_>, text: &str) -> PyResult<Py<PyList>> {
    let haystack = text.to_lowercase();
    let mut found: Vec<&str> = Vec::new();

    for &(label, keywords) in NEED_KEYWORD_DATA {
        if keywords.iter().any(|&kw| contains_keyword(&haystack, kw)) {
            found.push(label);
        }
    }

    let list = PyList::new_bound(py, found);
    Ok(list.unbind())
}

/// Estimate IPC-like severity phase (1-5) from text keywords.
#[pyfunction]
pub fn severity_from_text(text: &str) -> i32 {
    let h = text.to_lowercase();
    if ["catastroph", "famine", "system collapse", "mass casualty"]
        .iter()
        .any(|k| h.contains(k))
    {
        return 5;
    }
    if [
        "state of emergency",
        "emergency declaration",
        "severe",
        "widespread destruction",
    ]
    .iter()
    .any(|k| h.contains(k))
    {
        return 4;
    }
    if ["significant", "critical", "major", "crisis", "large-scale"]
        .iter()
        .any(|k| h.contains(k))
    {
        return 3;
    }
    if ["elevated", "moderate", "stressed", "warning"]
        .iter()
        .any(|k| h.contains(k))
    {
        return 2;
    }
    1
}

/// Return `true` if text contains risk or forecast language.
#[pyfunction]
pub fn is_risk_text(text: &str) -> bool {
    let h = text.to_lowercase();
    RISK_KEYWORD_DATA.iter().any(|&kw| h.contains(kw))
}

/// Detect a response actor from text.
///
/// Returns (actor_name, actor_type) tuple or None.
#[pyfunction]
pub fn detect_response_actor(text: &str) -> Option<(String, String)> {
    let h = text.to_lowercase();
    for &(keyword, actor_type) in RESPONSE_ACTORS {
        if contains_keyword(&h, keyword) {
            return Some((keyword.to_uppercase(), actor_type.to_string()));
        }
    }
    None
}

/// Detect an admin area name in text from a list of known areas.
///
/// Parameters
/// ----------
/// text : str
///     Evidence text to scan.
/// area_names : list[tuple[str, int]]
///     List of (area_name, admin_level) tuples from the gazetteer.
///
/// Returns
/// -------
/// tuple[str, int] | None
///     (matched_area_name, admin_level) or None.
#[pyfunction]
pub fn detect_admin_area(text: &str, area_names: Vec<(String, i32)>) -> Option<(String, i32)> {
    let h = text.to_lowercase();

    // Sort by admin level descending (prefer more specific matches)
    let mut sorted_areas = area_names;
    sorted_areas.sort_by(|a, b| b.1.cmp(&a.1));

    for (name, level) in &sorted_areas {
        if *level < 1 {
            continue;
        }
        let lower_name = name.to_lowercase();
        // Word-boundary match
        let pattern = format!(r"(?<!\w){}(?!\w)", regex::escape(&lower_name));
        if let Ok(re) = Regex::new(&pattern) {
            if Regex::is_match(&re, &h) {
                return Some((name.clone(), *level));
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_classify_impact_people() {
        assert_eq!(classify_impact_type("52 deaths confirmed"), "people_impact");
    }

    #[test]
    fn test_classify_impact_housing() {
        assert_eq!(
            classify_impact_type("houses destroyed and homes damaged"),
            "housing_lc_impact"
        );
    }

    #[test]
    fn test_classify_all_multi() {
        pyo3::prepare_freethreaded_python();
        let result = Python::with_gil(|py| {
            let list = classify_all_impact_types(py, "52 killed, 3 bridges destroyed, hospital collapsed").unwrap();
            let bound = list.bind(py);
            bound.iter().map(|i| i.extract::<String>().unwrap()).collect::<Vec<_>>()
        });
        assert!(result.contains(&"people_impact".to_string()), "expected people_impact in {result:?}");
        assert!(result.len() >= 2, "expected >= 2 impact types, got {result:?}");
    }

    #[test]
    fn test_classify_all_fallback() {
        pyo3::prepare_freethreaded_python();
        let result = Python::with_gil(|py| {
            let list = classify_all_impact_types(py, "general update with no keywords").unwrap();
            let bound = list.bind(py);
            bound.iter().map(|i| i.extract::<String>().unwrap()).collect::<Vec<_>>()
        });
        assert_eq!(result, vec!["people_impact".to_string()]);
    }

    #[test]
    fn test_classify_needs() {
        pyo3::prepare_freethreaded_python();
        let py_result = Python::with_gil(|py| {
            let list = classify_need_types(py, "food insecurity and water contamination").unwrap();
            let bound = list.bind(py);
            let items: Vec<String> = bound.iter().map(|i| i.extract::<String>().unwrap()).collect();
            items
        });
        assert!(py_result.contains(&"food_security".to_string()));
        assert!(py_result.contains(&"wash".to_string()));
    }

    #[test]
    fn test_severity() {
        assert_eq!(severity_from_text("catastrophic flooding"), 5);
        assert_eq!(severity_from_text("state of emergency declared"), 4);
        assert_eq!(severity_from_text("major damage reported"), 3);
        assert_eq!(severity_from_text("routine update"), 1);
    }

    #[test]
    fn test_risk_text() {
        assert!(is_risk_text("forecast shows continued rainfall"));
        assert!(!is_risk_text("the damage has been assessed"));
    }

    #[test]
    fn test_detect_actor() {
        let result = detect_response_actor("UNICEF is deploying supplies");
        assert_eq!(result, Some(("UNICEF".to_string(), "un_agency".to_string())));
    }
}

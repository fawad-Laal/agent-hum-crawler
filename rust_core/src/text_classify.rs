//! Text classification — keyword matching for humanitarian impacts, needs, severity.
//!
//! Replaces Python dict-scan loops with compiled Rust pattern matching.

use pyo3::prelude::*;
use pyo3::types::PyList;
use regex::Regex;

// ── Impact type keywords ────────────────────────────────────────────

struct KeywordSet {
    label: &'static str,
    keywords: &'static [&'static str],
}

static IMPACT_KEYWORDS: &[KeywordSet] = &[
    KeywordSet {
        label: "people_impact",
        keywords: &[
            "deaths", "killed", "fatalities", "dead", "missing",
            "injured", "casualties", "displaced", "evacuated",
        ],
    },
    KeywordSet {
        label: "housing_lc_impact",
        keywords: &[
            "houses destroyed", "houses damaged", "homes destroyed",
            "homes damaged", "housing", "shelter",
        ],
    },
    KeywordSet {
        label: "infrastructure_impact",
        keywords: &[
            "bridge", "road", "highway", "port", "airport",
            "power", "electricity", "grid", "infrastructure",
        ],
    },
    KeywordSet {
        label: "services_impact",
        keywords: &[
            "hospital", "health facility", "clinic", "school",
            "water supply", "sanitation",
        ],
    },
    KeywordSet {
        label: "systems_impact",
        keywords: &[
            "market", "supply chain", "food system", "agriculture",
            "fisheries", "livelihoods",
        ],
    },
];

static NEED_KEYWORDS: &[KeywordSet] = &[
    KeywordSet {
        label: "food_security",
        keywords: &[
            "food", "hunger", "nutrition", "malnutrition",
            "famine", "food insecurity", "crop", "harvest",
        ],
    },
    KeywordSet {
        label: "health",
        keywords: &[
            "health", "medical", "cholera", "malaria", "dengue",
            "disease", "epidemic", "outbreak", "medicine",
        ],
    },
    KeywordSet {
        label: "wash",
        keywords: &[
            "water", "sanitation", "hygiene", "wash",
            "contamination", "borehole", "latrine",
        ],
    },
    KeywordSet {
        label: "protection",
        keywords: &[
            "protection", "gbv", "child protection",
            "trafficking", "violence",
        ],
    },
    KeywordSet {
        label: "education",
        keywords: &[
            "school", "education", "learner", "student",
            "teacher", "classroom",
        ],
    },
    KeywordSet {
        label: "shelter",
        keywords: &[
            "shelter", "housing", "accommodation", "tent",
            "tarpaulin", "nfi",
        ],
    },
    KeywordSet {
        label: "logistics",
        keywords: &[
            "logistics", "transport", "access", "road",
            "bridge", "supply",
        ],
    },
];

static RISK_KEYWORDS: &[&str] = &[
    "forecast", "outlook", "prediction", "warning",
    "alert", "expected", "anticipated", "risk",
    "likelihood", "probability", "projection",
];

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
    // Simple substring for multi-word, word-boundary for single-word
    if keyword.contains(' ') {
        haystack.contains(keyword)
    } else {
        // Build a boundary-aware check
        if let Some(pos) = haystack.find(keyword) {
            let before_ok = pos == 0
                || !haystack.as_bytes()[pos - 1].is_ascii_alphanumeric();
            let after_pos = pos + keyword.len();
            let after_ok = after_pos >= haystack.len()
                || !haystack.as_bytes()[after_pos].is_ascii_alphanumeric();
            before_ok && after_ok
        } else {
            false
        }
    }
}

/// Classify the dominant impact type from text.
///
/// Returns one of: "people_impact", "housing_lc_impact",
/// "infrastructure_impact", "services_impact", "systems_impact".
#[pyfunction]
pub fn classify_impact_type(text: &str) -> String {
    let haystack = text.to_lowercase();
    let mut best_label = "people_impact";
    let mut best_score = 0i32;

    for kset in IMPACT_KEYWORDS {
        let score: i32 = kset
            .keywords
            .iter()
            .filter(|kw| contains_keyword(&haystack, kw))
            .count() as i32;
        if score > best_score {
            best_score = score;
            best_label = kset.label;
        }
    }
    best_label.to_string()
}

/// Find all need types mentioned in text.
///
/// Returns a list of need type strings, e.g. ["food_security", "wash"].
#[pyfunction]
pub fn classify_need_types(py: Python<'_>, text: &str) -> PyResult<Py<PyList>> {
    let haystack = text.to_lowercase();
    let mut found: Vec<String> = Vec::new();

    for kset in NEED_KEYWORDS {
        if kset.keywords.iter().any(|kw| contains_keyword(&haystack, kw)) {
            found.push(kset.label.to_string());
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

/// Check if text contains risk/forecast keywords.
#[pyfunction]
pub fn is_risk_text(text: &str) -> bool {
    let h = text.to_lowercase();
    RISK_KEYWORDS.iter().any(|kw| h.contains(kw))
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

//! Figure extraction — 4-pattern NLP regex for humanitarian text.
//!
//! Extracts numeric figures (deaths, displaced, affected, houses, etc.)
//! from evidence text using the same 4-pattern strategy as the Python
//! implementation but compiled to native regex for ~50-100x throughput.

use once_cell::sync::Lazy;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use regex::Regex;
use std::collections::HashMap;

// Pattern 1: NUM + keyword (e.g. "48,000 displaced")
static NUMBER_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        r"(?i)(\d[\d,]*(?:\.\d+)?)\s*(people|persons|individuals|deaths|dead|killed|displaced|injured|missing|houses|homes|affected|families|households|children|schools|health\s*facilit)"
    ).unwrap()
});

// Pattern 2: "death toll rises to NUM" / "kills NUM"
static TOLL_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        r"(?i)(?:death\s+toll|toll)\s+(?:rises?\s+to|hits?|reaches?|climbs?\s+to|stands?\s+at|now)\s+(\d[\d,]*)|(?:kills?|killed)\s+(\d[\d,]*)"
    ).unwrap()
});

// Pattern 3: "at least/over/more than NUM keyword"
static ATLEAST_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        r"(?i)(?:at\s+least|over|more\s+than|nearly|approximately|about|up\s+to|around|some)\s+(\d[\d,]*(?:\.\d+)?)\s*(people|persons|dead|killed|deaths|displaced|injured|missing|affected|houses|homes|children|families|schools|health)"
    ).unwrap()
});

// Pattern 4: "NUM killed/dead/deaths" at sentence level
static SENTENCE_FIGURE_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(?i)\b(\d[\d,]*)\b[^.]{0,30}\b(killed|dead|deaths|drowned|perished|fatalities)")
        .unwrap()
});

fn parse_number(raw: &str) -> Option<i64> {
    let cleaned: String = raw.replace(',', "");
    cleaned.parse::<f64>().ok().map(|f| f as i64)
}

fn label_to_key(label: &str) -> &'static str {
    let l = label.to_lowercase();
    let l = l.trim();
    match &*l {
        "deaths" | "dead" | "killed" => "deaths",
        "displaced" => "displaced",
        "injured" => "injured",
        "missing" => "missing",
        "houses" | "homes" => "houses_affected",
        "people" | "persons" | "individuals" | "affected" | "families" | "households" => {
            "people_affected"
        }
        "children" => "children_affected",
        "schools" => "schools_affected",
        _ if l.starts_with("health") => "health_facilities_affected",
        _ => "people_affected",
    }
}

fn accum(figures: &mut HashMap<String, i64>, key: &str, value: i64) {
    let entry = figures.entry(key.to_string()).or_insert(0);
    if value > *entry {
        *entry = value;
    }
}

/// Extract numeric humanitarian figures from text.
///
/// Returns a dict mapping figure keys (deaths, displaced, people_affected, etc.)
/// to their maximum observed integer values. Uses max() accumulation to prevent
/// double-counting across overlapping patterns.
///
/// Parameters
/// ----------
/// text : str
///     The evidence text to extract figures from.
///
/// Returns
/// -------
/// dict[str, int]
///     Extracted figures, e.g. {"deaths": 59, "displaced": 16000}.
#[pyfunction]
pub fn extract_figures(py: Python<'_>, text: &str) -> PyResult<Py<PyDict>> {
    let mut figures: HashMap<String, i64> = HashMap::new();

    // Pattern 1: standard NUM + keyword
    for cap in NUMBER_PATTERN.captures_iter(text) {
        if let (Some(num_match), Some(label_match)) = (cap.get(1), cap.get(2)) {
            if let Some(value) = parse_number(num_match.as_str()) {
                let key = label_to_key(label_match.as_str());
                accum(&mut figures, key, value);
            }
        }
    }

    // Pattern 2: "death toll rises to 59" / "kills 4"
    for cap in TOLL_PATTERN.captures_iter(text) {
        let raw = cap
            .get(1)
            .or_else(|| cap.get(2))
            .map(|m| m.as_str())
            .unwrap_or("");
        if let Some(value) = parse_number(raw) {
            if value > 0 {
                accum(&mut figures, "deaths", value);
            }
        }
    }

    // Pattern 3: "at least 48,000 displaced"
    for cap in ATLEAST_PATTERN.captures_iter(text) {
        if let (Some(num_match), Some(label_match)) = (cap.get(1), cap.get(2)) {
            if let Some(value) = parse_number(num_match.as_str()) {
                let key = label_to_key(label_match.as_str());
                accum(&mut figures, key, value);
            }
        }
    }

    // Pattern 4: "59 killed" / "40 dead" in sentence context
    for cap in SENTENCE_FIGURE_PATTERN.captures_iter(text) {
        if let Some(num_match) = cap.get(1) {
            if let Some(value) = parse_number(num_match.as_str()) {
                if value > 0 && value < 1_000_000 {
                    accum(&mut figures, "deaths", value);
                }
            }
        }
    }

    let dict = PyDict::new_bound(py);
    for (k, v) in &figures {
        dict.set_item(k, *v)?;
    }
    Ok(dict.unbind())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn extract(text: &str) -> HashMap<String, i64> {
        let mut figures: HashMap<String, i64> = HashMap::new();

        for cap in NUMBER_PATTERN.captures_iter(text) {
            if let (Some(num_match), Some(label_match)) = (cap.get(1), cap.get(2)) {
                if let Some(value) = parse_number(num_match.as_str()) {
                    let key = label_to_key(label_match.as_str());
                    accum(&mut figures, key, value);
                }
            }
        }
        for cap in TOLL_PATTERN.captures_iter(text) {
            let raw = cap
                .get(1)
                .or_else(|| cap.get(2))
                .map(|m| m.as_str())
                .unwrap_or("");
            if let Some(value) = parse_number(raw) {
                if value > 0 {
                    accum(&mut figures, "deaths", value);
                }
            }
        }
        for cap in ATLEAST_PATTERN.captures_iter(text) {
            if let (Some(num_match), Some(label_match)) = (cap.get(1), cap.get(2)) {
                if let Some(value) = parse_number(num_match.as_str()) {
                    let key = label_to_key(label_match.as_str());
                    accum(&mut figures, key, value);
                }
            }
        }
        for cap in SENTENCE_FIGURE_PATTERN.captures_iter(text) {
            if let Some(num_match) = cap.get(1) {
                if let Some(value) = parse_number(num_match.as_str()) {
                    if value > 0 && value < 1_000_000 {
                        accum(&mut figures, "deaths", value);
                    }
                }
            }
        }
        figures
    }

    #[test]
    fn test_basic_displaced() {
        let r = extract("48,000 displaced in Madagascar");
        assert_eq!(r.get("displaced"), Some(&48000));
    }

    #[test]
    fn test_death_toll() {
        let r = extract("death toll rises to 59 after cyclone");
        assert_eq!(r.get("deaths"), Some(&59));
    }

    #[test]
    fn test_at_least() {
        let r = extract("at least 158 dead and over 400,000 affected");
        assert_eq!(r.get("deaths"), Some(&158));
        assert_eq!(r.get("people_affected"), Some(&400000));
    }

    #[test]
    fn test_sentence_killed() {
        let r = extract("The storm 59 killed in the coastal region");
        assert_eq!(r.get("deaths"), Some(&59));
    }

    #[test]
    fn test_max_accumulation() {
        let r = extract("52 dead reported. Death toll rises to 59. At least 59 killed.");
        assert_eq!(r.get("deaths"), Some(&59));
    }

    #[test]
    fn test_no_false_displaced_as_deaths() {
        // Regression: "deaths and 16,000 displaced" should NOT count 16,000 as deaths
        let r = extract("158 deaths and 16,000 displaced across provinces");
        assert_eq!(r.get("deaths"), Some(&158));
        assert_eq!(r.get("displaced"), Some(&16000));
    }
}

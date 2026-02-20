//! Fuzzy deduplication — string similarity scoring.
//!
//! Replaces Python's difflib.SequenceMatcher with optimised Rust
//! implementation for O(n*m) string similarity and O(n^2) clustering.

use pyo3::prelude::*;
use pyo3::types::PyList;

/// Normalise text: casefold and collapse whitespace.
#[pyfunction]
pub fn normalize_text(text: &str) -> String {
    text.split_whitespace()
        .collect::<Vec<&str>>()
        .join(" ")
        .to_lowercase()
}

/// Compute similarity ratio between two strings (0.0 to 1.0).
///
/// Uses the same algorithm as Python's SequenceMatcher.ratio():
/// 2.0 * M / T where M = matches, T = total chars.
/// Implemented via longest common subsequence for accuracy.
#[pyfunction]
pub fn similarity_ratio(a: &str, b: &str) -> f64 {
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }

    let a_norm = normalize_text(a);
    let b_norm = normalize_text(b);
    let a_bytes = a_norm.as_bytes();
    let b_bytes = b_norm.as_bytes();
    let a_len = a_bytes.len();
    let b_len = b_bytes.len();

    // Quick length-ratio check to short-circuit obvious non-matches
    let len_ratio = a_len.min(b_len) as f64 / a_len.max(b_len) as f64;
    if len_ratio < 0.5 {
        return len_ratio;
    }

    // Compute matching characters via longest common subsequence
    let matches = lcs_length(a_bytes, b_bytes);
    2.0 * matches as f64 / (a_len + b_len) as f64
}

/// LCS length using two-row DP (space-optimised).
fn lcs_length(a: &[u8], b: &[u8]) -> usize {
    let m = a.len();
    let n = b.len();
    let mut prev = vec![0usize; n + 1];
    let mut curr = vec![0usize; n + 1];

    for i in 1..=m {
        for j in 1..=n {
            if a[i - 1] == b[j - 1] {
                curr[j] = prev[j - 1] + 1;
            } else {
                curr[j] = curr[j - 1].max(prev[j]);
            }
        }
        std::mem::swap(&mut prev, &mut curr);
        curr.fill(0);
    }
    prev[n]
}

/// Cluster a list of titles by fuzzy similarity.
///
/// Parameters
/// ----------
/// titles : list[str]
///     Titles to cluster.
/// threshold : float
///     Similarity threshold (0.0-1.0) for clustering. Default 0.90.
///
/// Returns
/// -------
/// list[list[int]]
///     List of clusters, each cluster is a list of original indices.
#[pyfunction]
#[pyo3(signature = (titles, threshold=0.90))]
pub fn cluster_titles(py: Python<'_>, titles: Vec<String>, threshold: f64) -> PyResult<Py<PyList>> {
    let normed: Vec<String> = titles.iter().map(|t| normalize_text(t)).collect();
    let mut clusters: Vec<Vec<usize>> = Vec::new();

    for (i, title) in normed.iter().enumerate() {
        let mut placed = false;
        for cluster in clusters.iter_mut() {
            let pivot_idx = cluster[0];
            let pivot = &normed[pivot_idx];
            let ratio = raw_similarity_ratio(title, pivot);
            if ratio >= threshold {
                cluster.push(i);
                placed = true;
                break;
            }
        }
        if !placed {
            clusters.push(vec![i]);
        }
    }

    let outer = PyList::empty_bound(py);
    for cluster in &clusters {
        let inner: pyo3::Bound<'_, PyList> = PyList::new_bound(py, cluster);
        outer.append(inner)?;
    }
    Ok(outer.unbind())
}

/// Internal similarity ratio on pre-normalised strings.
fn raw_similarity_ratio(a: &str, b: &str) -> f64 {
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let a_bytes = a.as_bytes();
    let b_bytes = b.as_bytes();
    let matches = lcs_length(a_bytes, b_bytes);
    2.0 * matches as f64 / (a_bytes.len() + b_bytes.len()) as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize() {
        assert_eq!(normalize_text("  Hello   World  "), "hello world");
    }

    #[test]
    fn test_identical() {
        let r = similarity_ratio("cyclone hits coast", "cyclone hits coast");
        assert!((r - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_similar() {
        let r = similarity_ratio(
            "Cyclone Gezani hits Madagascar coast",
            "Cyclone Gezani strikes Madagascar coastline",
        );
        assert!(r > 0.7);
    }

    #[test]
    fn test_dissimilar() {
        let r = similarity_ratio("earthquake in japan", "flooding in brazil");
        assert!(r < 0.5);
    }

    #[test]
    fn test_empty() {
        assert!((similarity_ratio("", "") - 1.0).abs() < 0.001);
        assert!((similarity_ratio("abc", "")).abs() < 0.001);
    }

    #[test]
    fn test_cluster() {
        pyo3::prepare_freethreaded_python();
        let titles = vec![
            "Cyclone Gezani hits Madagascar".to_string(),
            "Cyclone Gezani strikes Madagascar coast".to_string(),
            "Earthquake in Turkey".to_string(),
            "Earthquake strikes Turkey".to_string(),
        ];
        Python::with_gil(|py| {
            let result = cluster_titles(py, titles, 0.65).unwrap();
            let bound = result.bind(py);
            // Should have 2 clusters
            assert_eq!(bound.len(), 2);
        });
    }
}

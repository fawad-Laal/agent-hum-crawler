//! URL canonicalization — tracking parameter stripping.
//!
//! Cleans tracking params (utm_*, fbclid, gclid, etc.) from URLs
//! and extracts Google News redirect targets.

use pyo3::prelude::*;
use url::Url;

static TRACKING_QUERY_PREFIXES: &[&str] = &["utm_"];
static TRACKING_QUERY_KEYS: &[&str] = &["fbclid", "gclid", "oc", "ved", "cid"];

/// Strip tracking parameters from a URL.
///
/// Removes utm_*, fbclid, gclid, oc, ved, cid query parameters
/// and the fragment.
#[pyfunction]
pub fn strip_tracking_params(url_str: &str) -> String {
    let parsed = match Url::parse(url_str) {
        Ok(u) => u,
        Err(_) => return url_str.to_string(),
    };

    let mut clean = parsed.clone();
    // Collect clean query pairs
    let clean_pairs: Vec<(String, String)> = parsed
        .query_pairs()
        .filter(|(key, _)| {
            let lk = key.to_lowercase();
            if TRACKING_QUERY_KEYS.contains(&lk.as_str()) {
                return false;
            }
            if TRACKING_QUERY_PREFIXES.iter().any(|p| lk.starts_with(p)) {
                return false;
            }
            true
        })
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();

    // Rebuild query string
    if clean_pairs.is_empty() {
        clean.set_query(None);
    } else {
        let qs: Vec<String> = clean_pairs
            .iter()
            .map(|(k, v)| {
                if v.is_empty() {
                    k.clone()
                } else {
                    format!("{}={}", k, v)
                }
            })
            .collect();
        clean.set_query(Some(&qs.join("&")));
    }

    // Strip fragment
    clean.set_fragment(None);
    clean.to_string()
}

/// Canonicalize a URL: extract Google News targets and strip tracking params.
///
/// Parameters
/// ----------
/// url_str : str
///     The URL to canonicalize.
///
/// Returns
/// -------
/// str
///     The canonicalized URL.
#[pyfunction]
pub fn canonicalize_url(url_str: &str) -> String {
    let raw = url_str.trim();
    if raw.is_empty() {
        return raw.to_string();
    }

    // Try to extract Google News target URL
    if let Some(target) = extract_google_target(raw) {
        return strip_tracking_params(&target);
    }

    strip_tracking_params(raw)
}

/// Extract the real target URL from a Google News redirect.
fn extract_google_target(url_str: &str) -> Option<String> {
    let parsed = Url::parse(url_str).ok()?;
    let host = parsed.host_str()?;
    if !host.contains("news.google.") {
        return None;
    }

    for (key, value) in parsed.query_pairs() {
        let lk = key.to_lowercase();
        if matches!(lk.as_str(), "url" | "u" | "q") {
            let candidate = value.trim().to_string();
            if candidate.starts_with("http://") || candidate.starts_with("https://") {
                return Some(candidate);
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_strip_utm() {
        let result = strip_tracking_params(
            "https://example.com/article?id=42&utm_source=twitter&utm_medium=social",
        );
        assert_eq!(result, "https://example.com/article?id=42");
    }

    #[test]
    fn test_strip_fbclid() {
        let result = strip_tracking_params(
            "https://example.com/news?fbclid=abc123&page=1",
        );
        assert_eq!(result, "https://example.com/news?page=1");
    }

    #[test]
    fn test_no_params() {
        let result = strip_tracking_params("https://example.com/article");
        assert_eq!(result, "https://example.com/article");
    }

    #[test]
    fn test_google_news_redirect() {
        let result = canonicalize_url(
            "https://news.google.com/rss/articles?url=https%3A%2F%2Fexample.com%2Fstory&oc=5",
        );
        assert_eq!(result, "https://example.com/story");
    }

    #[test]
    fn test_empty() {
        assert_eq!(canonicalize_url(""), "");
        assert_eq!(canonicalize_url("  "), "");
    }
}

//! Performance-critical Rust extensions for Moltis humanitarian crawler.
//!
//! Accelerates four hot paths:
//! 1. Figure extraction (4-pattern NLP regex)
//! 2. Text classification (keyword matching for impacts/needs/severity)
//! 3. Fuzzy deduplication (string similarity scoring)
//! 4. URL canonicalization (tracking param stripping)

mod figure_extraction;
mod text_classify;
mod fuzzy_dedupe;
mod url_canonical;

use pyo3::prelude::*;

/// Moltis Rust Core — native accelerator for humanitarian text processing.
#[pymodule]
fn moltis_rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Figure extraction
    m.add_function(wrap_pyfunction!(figure_extraction::extract_figures, m)?)?;

    // Text classification
    m.add_function(wrap_pyfunction!(text_classify::classify_impact_type, m)?)?;
    m.add_function(wrap_pyfunction!(text_classify::classify_need_types, m)?)?;
    m.add_function(wrap_pyfunction!(text_classify::severity_from_text, m)?)?;
    m.add_function(wrap_pyfunction!(text_classify::is_risk_text, m)?)?;
    m.add_function(wrap_pyfunction!(text_classify::detect_response_actor, m)?)?;
    m.add_function(wrap_pyfunction!(text_classify::detect_admin_area, m)?)?;

    // Fuzzy deduplication
    m.add_function(wrap_pyfunction!(fuzzy_dedupe::similarity_ratio, m)?)?;
    m.add_function(wrap_pyfunction!(fuzzy_dedupe::cluster_titles, m)?)?;
    m.add_function(wrap_pyfunction!(fuzzy_dedupe::normalize_text, m)?)?;

    // URL canonicalization  
    m.add_function(wrap_pyfunction!(url_canonical::canonicalize_url, m)?)?;
    m.add_function(wrap_pyfunction!(url_canonical::strip_tracking_params, m)?)?;

    Ok(())
}

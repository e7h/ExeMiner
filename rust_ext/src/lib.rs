//! exeminer_rust
//!
//! A small PyO3 extension that accelerates the "find every occurrence of
//! any Nuitka magic header inside a byte buffer" step of ExeMiner.
//!
//! On large executables (multi-hundred-MB onefile builds) the pure-Python
//! `bytes.find(...)` loop in `core/nuitka_extractor.py` can get slow because
//! it re-scans overlapping regions for every one of the 6 magic headers.
//! This module does the same overlapping scan, but in native code using
//! `memchr::memmem`, which is SIMD-accelerated on x86_64/aarch64.
//!
//! Python-side usage (see core/nuitka_extractor.py):
//!
//!     import exeminer_rust
//!     # data: bytes, headers: list[bytes]
//!     results = exeminer_rust.find_headers(data, headers)
//!     # -> list[(offset: int, header: bytes)], sorted by offset,
//!     #    duplicates removed - semantically identical to the Python
//!     #    fallback loop.

use memchr::memmem;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

/// Find every (possibly overlapping) offset where `pattern` occurs inside
/// `haystack`. Mirrors the Python idiom:
///
///     off = 0
///     while True:
///         idx = haystack.find(pattern, off)
///         if idx == -1: break
///         yield idx
///         off = idx + 1
///
/// i.e. after a match, the next search resumes one byte later (not past
/// the whole pattern), so overlapping matches are still found.
fn find_all_overlapping(haystack: &[u8], pattern: &[u8]) -> Vec<usize> {
    let mut offsets = Vec::new();
    if pattern.is_empty() || haystack.len() < pattern.len() {
        return offsets;
    }

    let mut start = 0usize;
    while start + pattern.len() <= haystack.len() {
        match memmem::find(&haystack[start..], pattern) {
            Some(rel_idx) => {
                let abs_idx = start + rel_idx;
                offsets.push(abs_idx);
                start = abs_idx + 1;
            }
            None => break,
        }
    }
    offsets
}

/// Scan `data` for every occurrence of every pattern in `headers`.
///
/// Returns a list of `(offset, header_bytes)` tuples sorted by offset,
/// with exact duplicate `(offset, header)` pairs removed - matching the
/// `sorted(set(candidates), key=lambda x: x[0])` step done on the Python
/// side after this call.
#[pyfunction]
fn find_headers(
    py: Python<'_>,
    data: &[u8],
    headers: Vec<Vec<u8>>,
) -> PyResult<Vec<(usize, Py<PyBytes>)>> {
    let mut results: Vec<(usize, Vec<u8>)> = Vec::new();

    for header in &headers {
        for offset in find_all_overlapping(data, header) {
            results.push((offset, header.clone()));
        }
    }

    results.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
    results.dedup();

    let out = results
        .into_iter()
        .map(|(offset, header)| (offset, PyBytes::new_bound(py, &header).into()))
        .collect();

    Ok(out)
}

/// Convenience single-pattern search, exposed in case other parts of
/// ExeMiner (e.g. the PyInstaller MAGIC cookie search) want to reuse the
/// fast path without going through the multi-header API.
#[pyfunction]
fn find_pattern(data: &[u8], pattern: &[u8]) -> PyResult<Vec<usize>> {
    Ok(find_all_overlapping(data, pattern))
}

/// Python module definition. The module name here MUST match `module-name`
/// in pyproject.toml and the `name` under `[lib]` in Cargo.toml.
#[pymodule]
fn exeminer_rust(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(find_headers, m)?)?;
    m.add_function(wrap_pyfunction!(find_pattern, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}

//! Runs every vector in ../../spec (the port's copy of the shared spec).
//! The Rust port had a conformance runner but no test that ran it.
use std::path::PathBuf;

#[test]
fn all_spec_vectors_pass() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../spec");
    let r = iaiso_conformance::run_all(&root).expect("load spec");
    let failures: Vec<String> = [&r.pressure, &r.consent, &r.events, &r.policy]
        .iter()
        .flat_map(|s| s.iter())
        .filter(|v| !v.passed)
        .map(|v| format!("[{}] {}: {}", v.section, v.name, v.message))
        .collect();
    let (passed, total) = r.count_passed();
    assert!(failures.is_empty(), "conformance {passed}/{total}:\n{}", failures.join("\n"));
    assert_eq!(total, 72, "spec 1.1 has 72 vectors");
}

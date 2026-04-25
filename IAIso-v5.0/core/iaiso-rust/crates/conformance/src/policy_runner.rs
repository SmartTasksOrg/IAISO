use crate::VectorResult;
use iaiso_policy::build;
use serde::Deserialize;
use serde_json::Value;
use std::path::Path;

#[derive(Debug, Deserialize)]
struct ValidPolicyVector {
    name: String,
    #[serde(default)]
    description: String,
    document: Value,
    #[serde(default)]
    expected_pressure: Option<Value>,
    #[serde(default)]
    expected_consent: Option<Value>,
    #[serde(default)]
    expected_metadata: Option<Value>,
}

#[derive(Debug, Deserialize)]
struct InvalidPolicyVector {
    name: String,
    #[serde(default)]
    description: String,
    document: Value,
    expect_error_path: String,
}

#[derive(Debug, Deserialize)]
struct PolicyFile {
    valid: Vec<ValidPolicyVector>,
    invalid: Vec<InvalidPolicyVector>,
}

pub fn run_policy(spec_root: &Path) -> Result<Vec<VectorResult>, String> {
    let path = spec_root.join("policy").join("vectors.json");
    let data = std::fs::read(&path).map_err(|e| format!("read {}: {}", path.display(), e))?;
    let file: PolicyFile =
        serde_json::from_slice(&data).map_err(|e| format!("parse {}: {}", path.display(), e))?;

    let mut results = Vec::new();
    for v in file.valid {
        results.push(run_one_valid(v));
    }
    for v in file.invalid {
        results.push(run_one_invalid(v));
    }
    Ok(results)
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() <= crate::TOLERANCE
}

fn check_f64(label: &str, got: f64, want: Option<&Value>) -> Option<String> {
    if let Some(v) = want {
        if let Some(w) = v.as_f64() {
            if !close(got, w) {
                return Some(format!("{}: got {}, want {}", label, got, w));
            }
        }
    }
    None
}

fn run_one_valid(v: ValidPolicyVector) -> VectorResult {
    let mut r = VectorResult {
        section: "policy".to_string(),
        name: format!("valid/{}", v.name),
        passed: false,
        message: String::new(),
    };
    let p = match build(&v.document) {
        Ok(p) => p,
        Err(e) => {
            r.message = format!("build failed: {}", e);
            return r;
        }
    };

    if let Some(ep) = &v.expected_pressure {
        let map = match ep.as_object() {
            Some(m) => m,
            None => {
                r.message = "expected_pressure not an object".to_string();
                return r;
            }
        };
        for (label, got) in [
            ("token_coefficient", p.pressure.token_coefficient),
            ("tool_coefficient", p.pressure.tool_coefficient),
            ("depth_coefficient", p.pressure.depth_coefficient),
            ("dissipation_per_step", p.pressure.dissipation_per_step),
            ("dissipation_per_second", p.pressure.dissipation_per_second),
            ("escalation_threshold", p.pressure.escalation_threshold),
            ("release_threshold", p.pressure.release_threshold),
        ] {
            if let Some(msg) = check_f64(label, got, map.get(label)) {
                r.message = msg;
                return r;
            }
        }
        if let Some(want) = map.get("post_release_lock").and_then(Value::as_bool) {
            if p.pressure.post_release_lock != want {
                r.message = "post_release_lock mismatch".to_string();
                return r;
            }
        }
    }

    if let Some(ec) = &v.expected_consent {
        if let Some(map) = ec.as_object() {
            // issuer: vectors use null for "no issuer set"; our type uses Option<String>
            if let Some(want) = map.get("issuer") {
                let want_s = want.as_str();
                let got_s = p.consent.issuer.as_deref();
                if want_s != got_s {
                    r.message = format!(
                        "consent.issuer: got {:?}, want {:?}",
                        got_s, want_s
                    );
                    return r;
                }
            }
            if let Some(msg) = check_f64(
                "default_ttl_seconds",
                p.consent.default_ttl_seconds,
                map.get("default_ttl_seconds"),
            ) {
                r.message = msg;
                return r;
            }
            if let Some(want) = map.get("required_scopes").and_then(Value::as_array) {
                if want.len() != p.consent.required_scopes.len() {
                    r.message = "required_scopes length mismatch".to_string();
                    return r;
                }
            }
            if let Some(want) = map.get("allowed_algorithms").and_then(Value::as_array) {
                if want.len() != p.consent.allowed_algorithms.len() {
                    r.message = "allowed_algorithms length mismatch".to_string();
                    return r;
                }
            }
        }
    }

    if let Some(em) = &v.expected_metadata {
        if let Some(map) = em.as_object() {
            if map.len() != p.metadata.len() {
                r.message = format!(
                    "metadata size: got {}, want {}",
                    p.metadata.len(),
                    map.len()
                );
                return r;
            }
        }
    }

    r.passed = true;
    r
}

fn run_one_invalid(v: InvalidPolicyVector) -> VectorResult {
    let mut r = VectorResult {
        section: "policy".to_string(),
        name: format!("invalid/{}", v.name),
        passed: false,
        message: String::new(),
    };
    match build(&v.document) {
        Ok(_) => {
            r.message = format!(
                "expected error containing {:?}, got Ok",
                v.expect_error_path
            );
        }
        Err(e) => {
            let msg = e.to_string();
            if msg.contains(&v.expect_error_path) {
                r.passed = true;
            } else {
                r.message = format!(
                    "expected error containing {:?}, got {:?}",
                    v.expect_error_path, msg
                );
            }
        }
    }
    r
}

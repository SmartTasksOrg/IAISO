use crate::VectorResult;
use iaiso_consent::{
    scope_granted, ConsentError, Issuer, IssuerOptions, RevocationList, SignatureAlgorithm,
    Verifier, VerifierOptions,
};
use serde::Deserialize;
use std::path::Path;
use std::sync::Arc;

#[derive(Debug, Deserialize)]
struct ScopeMatchVector {
    name: String,
    granted: Vec<String>,
    requested: String,
    expected: bool,
}

#[derive(Debug, Deserialize)]
struct ScopeMatchErrorVector {
    name: String,
    granted: Vec<String>,
    requested: String,
    expect_error: String,
}

#[derive(Debug, Deserialize)]
struct ValidTokenExpected {
    sub: String,
    jti: String,
    scopes: Vec<String>,
    #[serde(default)]
    execution_id: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ValidTokenVector {
    name: String,
    token: String,
    #[serde(default = "default_alg")]
    algorithm: String,
    #[serde(default = "default_iss")]
    issuer: String,
    now: i64,
    expected: ValidTokenExpected,
}

#[derive(Debug, Deserialize)]
struct InvalidTokenVector {
    name: String,
    token: String,
    #[serde(default = "default_alg")]
    algorithm: String,
    #[serde(default = "default_iss")]
    issuer: String,
    now: i64,
    #[serde(default)]
    execution_id: Option<String>,
    expect_error: String,
}

#[derive(Debug, Deserialize)]
struct RoundtripIssue {
    subject: String,
    scopes: Vec<String>,
    ttl_seconds: i64,
    #[serde(default)]
    execution_id: Option<String>,
    #[serde(default)]
    metadata: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
struct RoundtripVector {
    name: String,
    issue: RoundtripIssue,
    #[serde(default)]
    verify_with_execution_id: Option<String>,
    #[serde(default = "default_alg")]
    algorithm: String,
    #[serde(default = "default_iss")]
    issuer: String,
    #[serde(default = "default_now")]
    now: i64,
    #[serde(default)]
    expected_after_verify_succeeds: bool,
}

fn default_now() -> i64 {
    1_700_000_000
}

fn default_alg() -> String {
    "HS256".to_string()
}
fn default_iss() -> String {
    "iaiso".to_string()
}

#[derive(Debug, Deserialize)]
struct ConsentFile {
    hs256_key_shared: String,
    scope_match: Vec<ScopeMatchVector>,
    scope_match_errors: Vec<ScopeMatchErrorVector>,
    valid_tokens: Vec<ValidTokenVector>,
    invalid_tokens: Vec<InvalidTokenVector>,
    issue_and_verify_roundtrip: Vec<RoundtripVector>,
}

fn algorithm_from(s: &str) -> SignatureAlgorithm {
    match s {
        "RS256" => SignatureAlgorithm::RS256,
        _ => SignatureAlgorithm::HS256,
    }
}

pub fn run_consent(spec_root: &Path) -> Result<Vec<VectorResult>, String> {
    let path = spec_root.join("consent").join("vectors.json");
    let data = std::fs::read(&path).map_err(|e| format!("read {}: {}", path.display(), e))?;
    let file: ConsentFile =
        serde_json::from_slice(&data).map_err(|e| format!("parse {}: {}", path.display(), e))?;

    let mut results = Vec::new();
    for v in file.scope_match {
        let mut r = VectorResult {
            section: "consent".to_string(),
            name: format!("scope_match/{}", v.name),
            passed: false,
            message: String::new(),
        };
        match scope_granted(&v.granted, &v.requested) {
            Ok(b) if b == v.expected => r.passed = true,
            Ok(b) => r.message = format!("got {}, want {}", b, v.expected),
            Err(e) => r.message = e.to_string(),
        }
        results.push(r);
    }
    for v in file.scope_match_errors {
        let mut r = VectorResult {
            section: "consent".to_string(),
            name: format!("scope_match_errors/{}", v.name),
            passed: false,
            message: String::new(),
        };
        match scope_granted(&v.granted, &v.requested) {
            Ok(_) => {
                r.message = format!("expected error containing {:?}, got Ok", v.expect_error);
            }
            Err(e) => {
                let msg = e.to_string();
                if !msg.contains(&v.expect_error) {
                    r.message = format!(
                        "expected error containing {:?}, got {:?}",
                        v.expect_error, msg
                    );
                } else {
                    r.passed = true;
                }
            }
        }
        results.push(r);
    }
    for v in file.valid_tokens {
        results.push(run_valid_token(&file.hs256_key_shared, v));
    }
    for v in file.invalid_tokens {
        results.push(run_invalid_token(&file.hs256_key_shared, v));
    }
    for v in file.issue_and_verify_roundtrip {
        results.push(run_roundtrip(&file.hs256_key_shared, v));
    }
    Ok(results)
}

fn run_valid_token(shared_key: &str, v: ValidTokenVector) -> VectorResult {
    let mut r = VectorResult {
        section: "consent".to_string(),
        name: format!("valid_tokens/{}", v.name),
        passed: false,
        message: String::new(),
    };
    let now = v.now;
    let verifier = Verifier::new(VerifierOptions {
        verification_key: shared_key.as_bytes().to_vec(),
        algorithm: algorithm_from(&v.algorithm),
        issuer: v.issuer.clone(),
        revocation_list: None,
        leeway_seconds: 5,
        clock: Some(Arc::new(move || now)),
    });
    match verifier.verify(&v.token, None) {
        Ok(scope) => {
            if scope.subject != v.expected.sub {
                r.message = format!("sub: got {}, want {}", scope.subject, v.expected.sub);
                return r;
            }
            if scope.jti != v.expected.jti {
                r.message = format!("jti: got {}, want {}", scope.jti, v.expected.jti);
                return r;
            }
            if scope.scopes != v.expected.scopes {
                r.message = "scopes mismatch".to_string();
                return r;
            }
            if scope.execution_id != v.expected.execution_id {
                r.message = format!(
                    "execution_id: got {:?}, want {:?}",
                    scope.execution_id, v.expected.execution_id
                );
                return r;
            }
            r.passed = true;
        }
        Err(e) => r.message = format!("verify failed: {}", e),
    }
    r
}

fn run_invalid_token(shared_key: &str, v: InvalidTokenVector) -> VectorResult {
    let mut r = VectorResult {
        section: "consent".to_string(),
        name: format!("invalid_tokens/{}", v.name),
        passed: false,
        message: String::new(),
    };
    let now = v.now;
    let verifier = Verifier::new(VerifierOptions {
        verification_key: shared_key.as_bytes().to_vec(),
        algorithm: algorithm_from(&v.algorithm),
        issuer: v.issuer.clone(),
        revocation_list: None,
        leeway_seconds: 5,
        clock: Some(Arc::new(move || now)),
    });
    match verifier.verify(&v.token, v.execution_id.as_deref()) {
        Ok(_) => r.message = "expected error, got Ok".to_string(),
        Err(e) => {
            let msg = e.to_string().to_lowercase();
            let ok = match v.expect_error.as_str() {
                "invalid" => matches!(e, ConsentError::InvalidToken(_)),
                "expired" => matches!(e, ConsentError::ExpiredToken) || msg.contains("expir"),
                "revoked" => matches!(e, ConsentError::RevokedToken(_)) || msg.contains("revok"),
                other => msg.contains(other),
            };
            if ok {
                r.passed = true;
            } else {
                r.message = format!("expected error of kind {}, got: {}", v.expect_error, e);
            }
        }
    }
    r
}

fn run_roundtrip(shared_key: &str, v: RoundtripVector) -> VectorResult {
    let mut r = VectorResult {
        section: "consent".to_string(),
        name: format!("roundtrip/{}", v.name),
        passed: false,
        message: String::new(),
    };
    let algo = algorithm_from(&v.algorithm);
    let now = v.now;

    let issuer = Issuer::new(IssuerOptions {
        signing_key: shared_key.as_bytes().to_vec(),
        algorithm: algo,
        issuer: v.issuer.clone(),
        default_ttl_seconds: 3600,
        clock: Some(Arc::new(move || now)),
    });
    let scope = match issuer.issue(
        &v.issue.subject,
        v.issue.scopes.clone(),
        v.issue.execution_id.clone(),
        Some(v.issue.ttl_seconds),
        v.issue.metadata.clone(),
    ) {
        Ok(s) => s,
        Err(e) => {
            r.message = format!("issue failed: {}", e);
            return r;
        }
    };

    let now_plus = v.now + 1;
    let verifier = Verifier::new(VerifierOptions {
        verification_key: shared_key.as_bytes().to_vec(),
        algorithm: algo,
        issuer: v.issuer.clone(),
        revocation_list: None,
        leeway_seconds: 5,
        clock: Some(Arc::new(move || now_plus)),
    });
    let verify_result = verifier.verify(&scope.token, v.verify_with_execution_id.as_deref());
    if v.expected_after_verify_succeeds {
        match verify_result {
            Ok(verified) => {
                if verified.subject != v.issue.subject {
                    r.message = format!(
                        "subject mismatch: {} vs {}",
                        verified.subject, v.issue.subject
                    );
                    return r;
                }
                if verified.scopes != v.issue.scopes {
                    r.message = "scopes mismatch".to_string();
                    return r;
                }
                let _ = RevocationList::new(); // exercise the type
                r.passed = true;
            }
            Err(e) => {
                r.message = format!("expected verify to succeed, failed: {}", e);
            }
        }
    } else if verify_result.is_err() {
        r.passed = true;
    } else {
        r.message = "expected verify to fail, succeeded".to_string();
    }
    r
}

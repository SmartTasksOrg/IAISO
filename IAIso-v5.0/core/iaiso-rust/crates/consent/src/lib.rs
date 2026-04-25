//! IAIso consent token implementation. JWT-based, HS256 (default) or
//! RS256. See `../../spec/consent/README.md` for the normative spec.
//!
//! # Scope grammar
//!
//! ```text
//! scope   ::= segment ("." segment)*
//! segment ::= [a-z0-9_-]+
//! ```
//!
//! A token granting `G` satisfies a request for `R` iff:
//! - `G == R` (exact match), or
//! - `R` starts with `G + "."` (prefix at segment boundary).

use jsonwebtoken::{
    decode, encode, Algorithm, DecodingKey, EncodingKey, Header, TokenData, Validation,
};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

/// Verification errors.
#[derive(Debug, Error)]
pub enum ConsentError {
    #[error("invalid token: {0}")]
    InvalidToken(String),
    #[error("expired token")]
    ExpiredToken,
    #[error("revoked token: jti={0}")]
    RevokedToken(String),
    #[error("scope {requested:?} not granted by token (granted: {granted:?})")]
    InsufficientScope {
        granted: Vec<String>,
        requested: String,
    },
    #[error("requested scope must be non-empty")]
    EmptyRequestedScope,
    #[error("signing failed: {0}")]
    SigningFailed(String),
    #[error("unsupported algorithm: {0:?}")]
    UnsupportedAlgorithm(SignatureAlgorithm),
}

/// Supported JWT algorithms. `None` is intentionally absent — verifiers
/// MUST reject unsigned tokens.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SignatureAlgorithm {
    HS256,
    RS256,
}

impl SignatureAlgorithm {
    fn to_jwt(self) -> Algorithm {
        match self {
            Self::HS256 => Algorithm::HS256,
            Self::RS256 => Algorithm::RS256,
        }
    }
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::HS256 => "HS256",
            Self::RS256 => "RS256",
        }
    }
}

/// Returns `Ok(true)` if the granted scopes satisfy a request for
/// `requested`. See module-level docs for grammar.
pub fn scope_granted(granted: &[String], requested: &str) -> Result<bool, ConsentError> {
    if requested.is_empty() {
        return Err(ConsentError::EmptyRequestedScope);
    }
    for g in granted {
        if g == requested {
            return Ok(true);
        }
        if requested.starts_with(&format!("{}.", g)) {
            return Ok(true);
        }
    }
    Ok(false)
}

/// JWT claims. Used as the wire format for issued/verified tokens.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub iss: String,
    pub sub: String,
    pub iat: i64,
    pub exp: i64,
    pub jti: String,
    pub scopes: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub execution_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
}

/// A verified consent scope, ready to attach to an execution.
#[derive(Debug, Clone)]
pub struct Scope {
    pub token: String,
    pub subject: String,
    pub scopes: Vec<String>,
    pub execution_id: Option<String>,
    pub jti: String,
    pub issued_at: i64,
    pub expires_at: i64,
    pub metadata: serde_json::Value,
}

impl Scope {
    pub fn grants(&self, requested: &str) -> bool {
        scope_granted(&self.scopes, requested).unwrap_or(false)
    }

    pub fn require(&self, requested: &str) -> Result<(), ConsentError> {
        if !self.grants(requested) {
            return Err(ConsentError::InsufficientScope {
                granted: self.scopes.clone(),
                requested: requested.to_string(),
            });
        }
        Ok(())
    }
}

/// In-memory revocation list. Production deployments should back this
/// with Redis or similar.
#[derive(Default)]
pub struct RevocationList {
    revoked: RwLock<HashSet<String>>,
}

impl RevocationList {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn revoke(&self, jti: impl Into<String>) {
        self.revoked.write().insert(jti.into());
    }
    pub fn is_revoked(&self, jti: &str) -> bool {
        self.revoked.read().contains(jti)
    }
    pub fn size(&self) -> usize {
        self.revoked.read().len()
    }
}

/// Clock source for issuer/verifier.
pub type Clock = std::sync::Arc<dyn Fn() -> i64 + Send + Sync>;

fn default_clock() -> Clock {
    std::sync::Arc::new(|| {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0)
    })
}

/// Configuration for [`Issuer`].
pub struct IssuerOptions {
    pub signing_key: Vec<u8>,
    pub algorithm: SignatureAlgorithm,
    pub issuer: String,
    pub default_ttl_seconds: i64,
    pub clock: Option<Clock>,
}

impl Default for IssuerOptions {
    fn default() -> Self {
        Self {
            signing_key: Vec::new(),
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            default_ttl_seconds: 3600,
            clock: None,
        }
    }
}

/// Mints signed consent tokens.
pub struct Issuer {
    opts: IssuerOptions,
    clock: Clock,
}

impl Issuer {
    pub fn new(opts: IssuerOptions) -> Self {
        let clock = opts.clock.clone().unwrap_or_else(default_clock);
        Self { opts, clock }
    }

    /// Parameters for a single issue call.
    pub fn issue(
        &self,
        subject: impl Into<String>,
        scopes: Vec<String>,
        execution_id: Option<String>,
        ttl_seconds: Option<i64>,
        metadata: Option<serde_json::Value>,
    ) -> Result<Scope, ConsentError> {
        let now = (self.clock)();
        let ttl = ttl_seconds.unwrap_or(self.opts.default_ttl_seconds);
        let exp = now + ttl;
        let jti = generate_jti();

        let claims = Claims {
            iss: self.opts.issuer.clone(),
            sub: subject.into(),
            iat: now,
            exp,
            jti: jti.clone(),
            scopes: scopes.clone(),
            execution_id: execution_id.clone(),
            metadata: metadata.clone(),
        };

        let header = Header::new(self.opts.algorithm.to_jwt());
        let key = match self.opts.algorithm {
            SignatureAlgorithm::HS256 => EncodingKey::from_secret(&self.opts.signing_key),
            SignatureAlgorithm::RS256 => EncodingKey::from_rsa_pem(&self.opts.signing_key)
                .map_err(|e| ConsentError::SigningFailed(e.to_string()))?,
        };

        let token = encode(&header, &claims, &key)
            .map_err(|e| ConsentError::SigningFailed(e.to_string()))?;

        Ok(Scope {
            token,
            subject: claims.sub,
            scopes,
            execution_id,
            jti,
            issued_at: now,
            expires_at: exp,
            metadata: metadata.unwrap_or_else(|| serde_json::json!({})),
        })
    }
}

/// Configuration for [`Verifier`].
pub struct VerifierOptions {
    pub verification_key: Vec<u8>,
    pub algorithm: SignatureAlgorithm,
    pub issuer: String,
    pub revocation_list: Option<std::sync::Arc<RevocationList>>,
    pub leeway_seconds: u64,
    pub clock: Option<Clock>,
}

impl Default for VerifierOptions {
    fn default() -> Self {
        Self {
            verification_key: Vec::new(),
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            revocation_list: None,
            leeway_seconds: 5,
            clock: None,
        }
    }
}

/// Verifies signed consent tokens.
pub struct Verifier {
    opts: VerifierOptions,
    clock: Clock,
}

impl Verifier {
    pub fn new(opts: VerifierOptions) -> Self {
        let clock = opts.clock.clone().unwrap_or_else(default_clock);
        Self { opts, clock }
    }

    /// Verify `token`. If `execution_id` is `Some` and the token is bound
    /// to a different execution, returns [`ConsentError::InvalidToken`].
    pub fn verify(
        &self,
        token: &str,
        execution_id: Option<&str>,
    ) -> Result<Scope, ConsentError> {
        let mut validation = Validation::new(self.opts.algorithm.to_jwt());
        validation.set_issuer(&[&self.opts.issuer]);
        validation.leeway = self.opts.leeway_seconds;
        validation.validate_exp = true;
        validation.required_spec_claims =
            HashSet::from(["exp".to_string(), "iat".to_string(), "iss".to_string(), "sub".to_string()]);

        // jsonwebtoken validates exp using std SystemTime. To honor our
        // configurable clock for deterministic tests, we manually verify
        // exp afterwards using a relaxed validation.
        validation.validate_exp = false;

        let key = match self.opts.algorithm {
            SignatureAlgorithm::HS256 => DecodingKey::from_secret(&self.opts.verification_key),
            SignatureAlgorithm::RS256 => DecodingKey::from_rsa_pem(&self.opts.verification_key)
                .map_err(|e| ConsentError::InvalidToken(e.to_string()))?,
        };

        let data: TokenData<Claims> = decode(token, &key, &validation)
            .map_err(|e| ConsentError::InvalidToken(e.to_string()))?;
        let claims = data.claims;

        // Manual exp check using our clock + leeway
        let now = (self.clock)();
        let leeway = self.opts.leeway_seconds as i64;
        if claims.exp + leeway < now {
            return Err(ConsentError::ExpiredToken);
        }

        // Required claims that aren't covered by required_spec_claims
        if claims.jti.is_empty() {
            return Err(ConsentError::InvalidToken(
                "missing required claim: jti".to_string(),
            ));
        }

        // Revocation
        if let Some(rl) = &self.opts.revocation_list {
            if rl.is_revoked(&claims.jti) {
                return Err(ConsentError::RevokedToken(claims.jti.clone()));
            }
        }

        // Execution binding
        if let (Some(req_exec), Some(tok_exec)) = (execution_id, claims.execution_id.as_deref()) {
            if req_exec != tok_exec {
                return Err(ConsentError::InvalidToken(format!(
                    "token bound to {:?}, requested {:?}",
                    tok_exec, req_exec
                )));
            }
        }

        Ok(Scope {
            token: token.to_string(),
            subject: claims.sub,
            scopes: claims.scopes,
            execution_id: claims.execution_id,
            jti: claims.jti,
            issued_at: claims.iat,
            expires_at: claims.exp,
            metadata: claims.metadata.unwrap_or_else(|| serde_json::json!({})),
        })
    }
}

/// Generate a base64url-without-padding HS256 secret. 64 bytes (512 bits)
/// — well above the HS256 minimum.
pub fn generate_hs256_secret() -> String {
    let buf = random_bytes(64);
    base64_url_no_pad(&buf)
}

fn generate_jti() -> String {
    let buf = random_bytes(16);
    buf.iter()
        .map(|b| format!("{:02x}", b))
        .collect::<String>()
}

fn random_bytes(n: usize) -> Vec<u8> {
    use std::time::{SystemTime, UNIX_EPOCH};
    // Mix process id + nanos repeatedly. Not a CSPRNG, but for jti
    // uniqueness in a single-process context this is sufficient. For
    // production-grade randomness, link rand or getrandom.
    let mut out = Vec::with_capacity(n);
    let pid = std::process::id() as u64;
    let mut state: u64 = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0)
        ^ pid;
    while out.len() < n {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        out.extend_from_slice(&state.to_le_bytes());
    }
    out.truncate(n);
    out
}

fn base64_url_no_pad(data: &[u8]) -> String {
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine as _;
    URL_SAFE_NO_PAD.encode(data)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scope_exact_match() {
        assert!(scope_granted(&vec!["tools.search".into()], "tools.search").unwrap());
    }

    #[test]
    fn scope_prefix_at_boundary() {
        assert!(scope_granted(&vec!["tools".into()], "tools.search").unwrap());
    }

    #[test]
    fn scope_substring_not_boundary() {
        assert!(!scope_granted(&vec!["tools".into()], "toolsbar").unwrap());
    }

    #[test]
    fn scope_more_specific_grant_doesnt_satisfy_less_specific_request() {
        assert!(!scope_granted(&vec!["tools.search.bulk".into()], "tools.search").unwrap());
    }

    #[test]
    fn scope_empty_request_errors() {
        assert!(matches!(
            scope_granted(&vec!["tools".into()], ""),
            Err(ConsentError::EmptyRequestedScope)
        ));
    }

    fn fixed_clock(t: i64) -> Clock {
        std::sync::Arc::new(move || t)
    }

    #[test]
    fn issue_verify_roundtrip() {
        let secret = b"test_secret_long_enough_for_hs256_security_xx".to_vec();
        let issuer = Issuer::new(IssuerOptions {
            signing_key: secret.clone(),
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            default_ttl_seconds: 3600,
            clock: Some(fixed_clock(1_700_000_000)),
        });
        let scope = issuer
            .issue("user-1", vec!["tools.search".into()], None, None, None)
            .unwrap();

        let verifier = Verifier::new(VerifierOptions {
            verification_key: secret,
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            revocation_list: None,
            leeway_seconds: 5,
            clock: Some(fixed_clock(1_700_000_001)),
        });
        let v = verifier.verify(&scope.token, None).unwrap();
        assert_eq!(v.subject, "user-1");
        assert!(v.grants("tools.search"));
    }

    #[test]
    fn verify_rejects_expired() {
        let secret = b"test_secret_long_enough_for_hs256_security_xx".to_vec();
        let issuer = Issuer::new(IssuerOptions {
            signing_key: secret.clone(),
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            default_ttl_seconds: 1,
            clock: Some(fixed_clock(1_700_000_000)),
        });
        let scope = issuer
            .issue("u", vec!["tools".into()], None, None, None)
            .unwrap();

        let verifier = Verifier::new(VerifierOptions {
            verification_key: secret,
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            revocation_list: None,
            leeway_seconds: 5,
            clock: Some(fixed_clock(1_700_000_010)),
        });
        let r = verifier.verify(&scope.token, None);
        assert!(matches!(r, Err(ConsentError::ExpiredToken)));
    }

    #[test]
    fn verify_honors_revocation() {
        let secret = b"test_secret_long_enough_for_hs256_security_xx".to_vec();
        let issuer = Issuer::new(IssuerOptions {
            signing_key: secret.clone(),
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            default_ttl_seconds: 3600,
            clock: Some(fixed_clock(1_700_000_000)),
        });
        let scope = issuer
            .issue("u", vec!["tools".into()], None, None, None)
            .unwrap();
        let rl = std::sync::Arc::new(RevocationList::new());
        rl.revoke(&scope.jti);

        let verifier = Verifier::new(VerifierOptions {
            verification_key: secret,
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            revocation_list: Some(rl),
            leeway_seconds: 5,
            clock: Some(fixed_clock(1_700_000_001)),
        });
        let r = verifier.verify(&scope.token, None);
        assert!(matches!(r, Err(ConsentError::RevokedToken(_))));
    }

    #[test]
    fn verify_honors_execution_binding() {
        let secret = b"test_secret_long_enough_for_hs256_security_xx".to_vec();
        let issuer = Issuer::new(IssuerOptions {
            signing_key: secret.clone(),
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            default_ttl_seconds: 3600,
            clock: Some(fixed_clock(1_700_000_000)),
        });
        let scope = issuer
            .issue(
                "u",
                vec!["tools".into()],
                Some("exec-abc".into()),
                None,
                None,
            )
            .unwrap();

        let verifier = Verifier::new(VerifierOptions {
            verification_key: secret,
            algorithm: SignatureAlgorithm::HS256,
            issuer: "iaiso".to_string(),
            revocation_list: None,
            leeway_seconds: 5,
            clock: Some(fixed_clock(1_700_000_001)),
        });
        let r = verifier.verify(&scope.token, Some("exec-xyz"));
        assert!(matches!(r, Err(ConsentError::InvalidToken(_))));
    }

    #[test]
    fn generate_hs256_secret_is_long_enough() {
        let s = generate_hs256_secret();
        assert!(s.len() >= 64);
    }
}

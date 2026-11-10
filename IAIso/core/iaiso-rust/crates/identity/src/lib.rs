//! IAIso OIDC identity integration.
//!
//! Verifies access/ID tokens from Okta, Auth0, Azure AD, or any
//! conforming OIDC provider, and mints IAIso [`Scope`]s from validated
//! identities.
//!
//! JWKS fetching is the caller's responsibility — we expose
//! [`OidcVerifier::verify_with_jwks`] taking pre-fetched JWKS bytes.
//! This keeps the crate HTTP-free; users can plug in `reqwest` or any
//! other HTTP client to fetch the discovery doc and JWKS.

use iaiso_consent::{Issuer, Scope};
use jsonwebtoken::{decode, decode_header, Algorithm, DecodingKey, TokenData, Validation};
use parking_lot::RwLock;
use serde::Deserialize;
use serde_json::{Map, Value};
use std::collections::HashSet;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum IdentityError {
    #[error("oidc: invalid token: {0}")]
    InvalidToken(String),
    #[error("oidc: aud mismatch (expected {expected:?})")]
    AudienceMismatch { expected: String },
    #[error("oidc: kid {0} not found in JWKS")]
    KidNotFound(String),
    #[error("oidc: unsupported key type {0}")]
    UnsupportedKeyType(String),
    #[error("oidc: jwks parse: {0}")]
    JwksParse(String),
    #[error("oidc: issue failed: {0}")]
    IssueFailed(String),
}

/// A single key from a JWKS document.
#[derive(Debug, Clone, Deserialize)]
pub struct Jwk {
    pub kty: String,
    pub kid: String,
    #[serde(default)]
    pub alg: Option<String>,
    #[serde(default)]
    pub r#use: Option<String>,
    #[serde(default)]
    pub n: Option<String>,
    #[serde(default)]
    pub e: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Jwks {
    pub keys: Vec<Jwk>,
}

/// Configuration for an [`OidcVerifier`].
#[derive(Debug, Clone)]
pub struct ProviderConfig {
    /// Discovery URL, e.g. `https://acme.okta.com/.well-known/openid-configuration`.
    /// Not fetched by this crate — see crate docs.
    pub discovery_url: Option<String>,
    /// Direct JWKS URL.
    pub jwks_url: Option<String>,
    /// Expected `iss` claim. Empty means trust discovery.
    pub issuer: Option<String>,
    /// Expected `aud` claim. Empty disables aud check.
    pub audience: Option<String>,
    /// Allowed signing algorithms. Defaults to RS256.
    pub allowed_algorithms: Vec<String>,
    /// Leeway for `exp` validation, in seconds. Default 5.
    pub leeway_seconds: u64,
}

impl Default for ProviderConfig {
    fn default() -> Self {
        Self {
            discovery_url: None,
            jwks_url: None,
            issuer: None,
            audience: None,
            allowed_algorithms: vec!["RS256".to_string()],
            leeway_seconds: 5,
        }
    }
}

/// Build a `ProviderConfig` for Okta.
pub fn okta_config(domain: &str, audience: &str) -> ProviderConfig {
    ProviderConfig {
        discovery_url: Some(format!("https://{}/.well-known/openid-configuration", domain)),
        jwks_url: None,
        issuer: Some(format!("https://{}", domain)),
        audience: Some(audience.to_string()),
        allowed_algorithms: vec!["RS256".to_string()],
        leeway_seconds: 5,
    }
}

/// Build a `ProviderConfig` for Auth0.
pub fn auth0_config(domain: &str, audience: &str) -> ProviderConfig {
    ProviderConfig {
        discovery_url: Some(format!("https://{}/.well-known/openid-configuration", domain)),
        jwks_url: None,
        issuer: Some(format!("https://{}/", domain)),
        audience: Some(audience.to_string()),
        allowed_algorithms: vec!["RS256".to_string()],
        leeway_seconds: 5,
    }
}

/// Build a `ProviderConfig` for Azure AD / Entra. `v2` selects between
/// the v1 and v2.0 endpoints.
pub fn azure_ad_config(tenant: &str, audience: &str, v2: bool) -> ProviderConfig {
    let base = if v2 {
        format!("https://login.microsoftonline.com/{}/v2.0", tenant)
    } else {
        format!("https://login.microsoftonline.com/{}", tenant)
    };
    ProviderConfig {
        discovery_url: Some(format!("{}/.well-known/openid-configuration", base)),
        jwks_url: None,
        issuer: Some(base),
        audience: Some(audience.to_string()),
        allowed_algorithms: vec!["RS256".to_string()],
        leeway_seconds: 5,
    }
}

/// OIDC verifier. Holds a cached JWKS document.
pub struct OidcVerifier {
    cfg: ProviderConfig,
    jwks: RwLock<Option<Jwks>>,
}

impl OidcVerifier {
    pub fn new(cfg: ProviderConfig) -> Self {
        Self {
            cfg,
            jwks: RwLock::new(None),
        }
    }

    /// Inject pre-fetched JWKS bytes into the verifier's cache. Use
    /// this to avoid taking an HTTP dependency in this crate.
    pub fn set_jwks_from_bytes(&self, body: &[u8]) -> Result<(), IdentityError> {
        let jwks: Jwks = serde_json::from_slice(body)
            .map_err(|e| IdentityError::JwksParse(e.to_string()))?;
        *self.jwks.write() = Some(jwks);
        Ok(())
    }

    /// Verify `token` against the cached JWKS and validate claims.
    pub fn verify(&self, token: &str) -> Result<Map<String, Value>, IdentityError> {
        let header = decode_header(token)
            .map_err(|e| IdentityError::InvalidToken(e.to_string()))?;
        let kid = header
            .kid
            .clone()
            .unwrap_or_default();

        let jwks_guard = self.jwks.read();
        let jwks = jwks_guard
            .as_ref()
            .ok_or_else(|| IdentityError::JwksParse("JWKS not loaded".to_string()))?;

        let jwk = if let Some(k) = jwks.keys.iter().find(|k| k.kid == kid) {
            k
        } else if jwks.keys.len() == 1 && kid.is_empty() {
            &jwks.keys[0]
        } else {
            return Err(IdentityError::KidNotFound(kid));
        };

        if jwk.kty != "RSA" {
            return Err(IdentityError::UnsupportedKeyType(jwk.kty.clone()));
        }
        let n = jwk
            .n
            .as_deref()
            .ok_or_else(|| IdentityError::JwksParse("missing n".to_string()))?;
        let e = jwk
            .e
            .as_deref()
            .ok_or_else(|| IdentityError::JwksParse("missing e".to_string()))?;
        let key = DecodingKey::from_rsa_components(n, e)
            .map_err(|err| IdentityError::JwksParse(err.to_string()))?;

        let mut validation = Validation::new(Algorithm::RS256);
        if let Some(iss) = &self.cfg.issuer {
            validation.set_issuer(&[iss]);
        }
        validation.leeway = self.cfg.leeway_seconds;

        let data: TokenData<Value> = decode(token, &key, &validation)
            .map_err(|err| IdentityError::InvalidToken(err.to_string()))?;
        let claims = match data.claims {
            Value::Object(m) => m,
            _ => {
                return Err(IdentityError::InvalidToken(
                    "claims not an object".to_string(),
                ))
            }
        };

        if let Some(want) = &self.cfg.audience {
            let ok = match claims.get("aud") {
                Some(Value::String(s)) => s == want,
                Some(Value::Array(arr)) => arr.iter().any(|v| v.as_str() == Some(want.as_str())),
                _ => false,
            };
            if !ok {
                return Err(IdentityError::AudienceMismatch {
                    expected: want.clone(),
                });
            }
        }
        Ok(claims)
    }
}

/// Configures how OIDC claims become IAIso scopes.
#[derive(Debug, Clone, Default)]
pub struct ScopeMapping {
    /// OIDC claim names to interpret as direct scope lists.
    /// Default: `["scp", "scope", "permissions"]`.
    pub direct_claims: Vec<String>,
    /// Map from group/role names to scope lists.
    pub group_to_scopes: std::collections::HashMap<String, Vec<String>>,
    /// Scopes to grant unconditionally for every verified identity.
    pub always_grant: Vec<String>,
}

/// Convert a verified claims map into a deduplicated list of scopes.
pub fn derive_scopes(claims: &Map<String, Value>, mapping: &ScopeMapping) -> Vec<String> {
    let direct_claims = if mapping.direct_claims.is_empty() {
        vec!["scp".to_string(), "scope".to_string(), "permissions".to_string()]
    } else {
        mapping.direct_claims.clone()
    };

    let mut seen = HashSet::new();
    let mut out: Vec<String> = Vec::new();
    let mut add = |s: String| {
        if !s.is_empty() && seen.insert(s.clone()) {
            out.push(s);
        }
    };

    for c in &direct_claims {
        if let Some(v) = claims.get(c) {
            match v {
                Value::String(s) => {
                    for token in s.split(|c: char| c == ' ' || c == ',' || c == '\t' || c == '\n') {
                        add(token.to_string());
                    }
                }
                Value::Array(arr) => {
                    for item in arr {
                        if let Some(s) = item.as_str() {
                            add(s.to_string());
                        }
                    }
                }
                _ => {}
            }
        }
    }

    let mut groups: Vec<String> = Vec::new();
    for c in &["groups", "roles"] {
        if let Some(v) = claims.get(*c) {
            if let Some(arr) = v.as_array() {
                for item in arr {
                    if let Some(s) = item.as_str() {
                        groups.push(s.to_string());
                    }
                }
            }
        }
    }
    for g in groups {
        if let Some(scopes) = mapping.group_to_scopes.get(&g) {
            for s in scopes {
                add(s.clone());
            }
        }
    }
    for s in &mapping.always_grant {
        add(s.clone());
    }
    out
}

/// Mint an IAIso consent scope from a verified OIDC identity.
pub fn issue_from_oidc(
    verifier: &OidcVerifier,
    issuer: &Issuer,
    token: &str,
    mapping: &ScopeMapping,
    ttl_seconds: i64,
    execution_id: Option<String>,
) -> Result<Scope, IdentityError> {
    let claims = verifier.verify(token)?;
    let subject = claims
        .get("sub")
        .and_then(Value::as_str)
        .unwrap_or("unknown")
        .to_string();
    let scopes = derive_scopes(&claims, mapping);
    let mut metadata = Map::new();
    if let Some(iss) = claims.get("iss") {
        metadata.insert("oidc_iss".to_string(), iss.clone());
    }
    if let Some(jti) = claims.get("jti") {
        metadata.insert("oidc_jti".to_string(), jti.clone());
    }
    if let Some(aud) = claims.get("aud") {
        metadata.insert("oidc_aud".to_string(), aud.clone());
    }
    let metadata_value = if metadata.is_empty() {
        None
    } else {
        Some(Value::Object(metadata))
    };
    let _ = SystemTime::now().duration_since(UNIX_EPOCH); // silence unused
    issuer
        .issue(subject, scopes, execution_id, Some(ttl_seconds), metadata_value)
        .map_err(|e| IdentityError::IssueFailed(e.to_string()))
}

// SystemTime import retained for future timestamp helpers
#[allow(dead_code)]
fn _silence_unused() {
    let _ = SystemTime::now().duration_since(UNIX_EPOCH);
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn derive_direct_claim_string() {
        let claims = json!({"scope": "tools.search tools.fetch"});
        let m = claims.as_object().unwrap().clone();
        let out = derive_scopes(&m, &ScopeMapping::default());
        assert!(out.contains(&"tools.search".to_string()));
        assert!(out.contains(&"tools.fetch".to_string()));
    }

    #[test]
    fn derive_direct_claim_array() {
        let claims = json!({"scp": ["a.b", "c"]});
        let m = claims.as_object().unwrap().clone();
        let out = derive_scopes(&m, &ScopeMapping::default());
        assert_eq!(out, vec!["a.b", "c"]);
    }

    #[test]
    fn derive_group_to_scopes() {
        let claims = json!({"groups": ["engineers"]});
        let m = claims.as_object().unwrap().clone();
        let mut g = std::collections::HashMap::new();
        g.insert(
            "engineers".to_string(),
            vec!["tools.search".to_string(), "tools.fetch".to_string()],
        );
        let mapping = ScopeMapping {
            direct_claims: vec![],
            group_to_scopes: g,
            always_grant: vec![],
        };
        let out = derive_scopes(&m, &mapping);
        assert!(out.contains(&"tools.search".to_string()));
        assert!(out.contains(&"tools.fetch".to_string()));
    }

    #[test]
    fn always_grant_added() {
        let claims = json!({});
        let m = claims.as_object().unwrap().clone();
        let mapping = ScopeMapping {
            direct_claims: vec![],
            group_to_scopes: Default::default(),
            always_grant: vec!["base".to_string()],
        };
        let out = derive_scopes(&m, &mapping);
        assert_eq!(out, vec!["base"]);
    }

    #[test]
    fn presets_have_expected_endpoints() {
        let okta = okta_config("acme.okta.com", "api");
        assert!(okta.discovery_url.unwrap().contains("acme.okta.com"));

        let auth0 = auth0_config("acme.auth0.com", "api");
        assert!(auth0.issuer.unwrap().ends_with('/'));

        let azure_v2 = azure_ad_config("tenant-id", "api", true);
        assert!(azure_v2.discovery_url.unwrap().contains("v2.0"));
    }
}

//! IAIso policy-as-code loader.
//!
//! See `../../spec/policy/README.md` for the normative format and
//! `../../spec/policy/vectors.json` for the 17 conformance vectors.

use iaiso_core::PressureConfig;
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::Path;
use thiserror::Error;

/// Errors produced when parsing or validating a policy.
#[derive(Debug, Error)]
pub enum PolicyError {
    #[error("{0}")]
    Validation(String),
    #[error("JSON parse failed: {0}")]
    Json(#[from] serde_json::Error),
    #[error("YAML parse failed: {0}")]
    Yaml(#[from] serde_yaml::Error),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("unsupported policy file extension: {0} (expected .json, .yaml, or .yml)")]
    UnsupportedExtension(String),
}

/// Aggregator name. Wire-format strings.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AggregatorKind {
    Sum,
    Mean,
    Max,
    WeightedSum,
}

impl AggregatorKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Sum => "sum",
            Self::Mean => "mean",
            Self::Max => "max",
            Self::WeightedSum => "weighted_sum",
        }
    }
}

/// Trait for aggregators. Implementations operate on per-execution
/// pressures returning a single aggregate.
pub trait Aggregator: Send + Sync {
    fn name(&self) -> AggregatorKind;
    fn aggregate(&self, pressures: &BTreeMap<String, f64>) -> f64;
}

pub struct SumAggregator;
impl Aggregator for SumAggregator {
    fn name(&self) -> AggregatorKind {
        AggregatorKind::Sum
    }
    fn aggregate(&self, p: &BTreeMap<String, f64>) -> f64 {
        p.values().sum()
    }
}

pub struct MeanAggregator;
impl Aggregator for MeanAggregator {
    fn name(&self) -> AggregatorKind {
        AggregatorKind::Mean
    }
    fn aggregate(&self, p: &BTreeMap<String, f64>) -> f64 {
        if p.is_empty() {
            0.0
        } else {
            p.values().sum::<f64>() / p.len() as f64
        }
    }
}

pub struct MaxAggregator;
impl Aggregator for MaxAggregator {
    fn name(&self) -> AggregatorKind {
        AggregatorKind::Max
    }
    fn aggregate(&self, p: &BTreeMap<String, f64>) -> f64 {
        p.values().cloned().fold(0.0_f64, f64::max)
    }
}

pub struct WeightedSumAggregator {
    pub weights: BTreeMap<String, f64>,
    pub default_weight: f64,
}

impl Aggregator for WeightedSumAggregator {
    fn name(&self) -> AggregatorKind {
        AggregatorKind::WeightedSum
    }
    fn aggregate(&self, p: &BTreeMap<String, f64>) -> f64 {
        p.iter()
            .map(|(k, v)| {
                self.weights
                    .get(k)
                    .copied()
                    .unwrap_or(self.default_weight)
                    * v
            })
            .sum()
    }
}

/// Coordinator-section configuration.
#[derive(Debug, Clone, Copy)]
pub struct CoordinatorConfig {
    pub escalation_threshold: f64,
    pub release_threshold: f64,
    pub notify_cooldown_seconds: f64,
}

impl Default for CoordinatorConfig {
    fn default() -> Self {
        Self {
            escalation_threshold: 5.0,
            release_threshold: 8.0,
            notify_cooldown_seconds: 1.0,
        }
    }
}

/// Consent-section configuration.
#[derive(Debug, Clone)]
pub struct ConsentPolicy {
    pub issuer: Option<String>,
    pub default_ttl_seconds: f64,
    pub required_scopes: Vec<String>,
    pub allowed_algorithms: Vec<String>,
}

impl Default for ConsentPolicy {
    fn default() -> Self {
        Self {
            issuer: None,
            default_ttl_seconds: 3600.0,
            required_scopes: vec![],
            allowed_algorithms: vec!["HS256".to_string(), "RS256".to_string()],
        }
    }
}

/// Assembled, validated policy document.
pub struct Policy {
    pub version: String,
    pub pressure: PressureConfig,
    pub coordinator: CoordinatorConfig,
    pub consent: ConsentPolicy,
    pub aggregator: Box<dyn Aggregator>,
    pub metadata: serde_json::Map<String, Value>,
}

impl std::fmt::Debug for Policy {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Policy")
            .field("version", &self.version)
            .field("pressure", &self.pressure)
            .field("coordinator", &self.coordinator)
            .field("consent", &self.consent)
            .field("aggregator", &self.aggregator.name())
            .field("metadata", &self.metadata)
            .finish()
    }
}

fn validate_scope_string(s: &str) -> bool {
    if s.is_empty() {
        return false;
    }
    for seg in s.split('.') {
        if seg.is_empty() {
            return false;
        }
        for c in seg.chars() {
            if !(c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_' || c == '-') {
                return false;
            }
        }
    }
    true
}

fn extract_f64(v: &Value) -> Option<f64> {
    v.as_f64().or_else(|| v.as_i64().map(|n| n as f64))
}

/// Validate a parsed document against the normative rules in
/// `../../spec/policy/README.md`. Returns an error on the first
/// violation.
pub fn validate(doc: &Value) -> Result<(), PolicyError> {
    let map = doc.as_object().ok_or_else(|| {
        PolicyError::Validation("$: policy document must be a mapping".to_string())
    })?;

    let version = map
        .get("version")
        .ok_or_else(|| PolicyError::Validation("$: required property 'version' missing".to_string()))?;
    let version_s = version.as_str().ok_or_else(|| {
        PolicyError::Validation(format!("$.version: must be exactly \"1\", got {}", version))
    })?;
    if version_s != "1" {
        return Err(PolicyError::Validation(format!(
            "$.version: must be exactly \"1\", got {}",
            version
        )));
    }

    if let Some(pressure) = map.get("pressure") {
        let p_obj = pressure.as_object().ok_or_else(|| {
            PolicyError::Validation("$.pressure: must be a mapping".to_string())
        })?;
        for f in &[
            "token_coefficient",
            "tool_coefficient",
            "depth_coefficient",
            "dissipation_per_step",
            "dissipation_per_second",
        ] {
            if let Some(v) = p_obj.get(*f) {
                let n = extract_f64(v).ok_or_else(|| {
                    PolicyError::Validation(format!("$.pressure.{}: expected number", f))
                })?;
                if n < 0.0 {
                    return Err(PolicyError::Validation(format!(
                        "$.pressure.{}: must be non-negative (got {})",
                        f, n
                    )));
                }
            }
        }
        for f in &["escalation_threshold", "release_threshold"] {
            if let Some(v) = p_obj.get(*f) {
                let n = extract_f64(v).ok_or_else(|| {
                    PolicyError::Validation(format!("$.pressure.{}: expected number", f))
                })?;
                if !(0.0..=1.0).contains(&n) {
                    return Err(PolicyError::Validation(format!(
                        "$.pressure.{}: must be in [0, 1] (got {})",
                        f, n
                    )));
                }
            }
        }
        if let Some(v) = p_obj.get("post_release_lock") {
            if !v.is_boolean() {
                return Err(PolicyError::Validation(
                    "$.pressure.post_release_lock: expected boolean".to_string(),
                ));
            }
        }
        if let (Some(esc), Some(rel)) = (
            p_obj.get("escalation_threshold").and_then(extract_f64),
            p_obj.get("release_threshold").and_then(extract_f64),
        ) {
            if rel <= esc {
                return Err(PolicyError::Validation(format!(
                    "$.pressure.release_threshold: must exceed escalation_threshold ({} <= {})",
                    rel, esc
                )));
            }
        }
    }

    if let Some(coord) = map.get("coordinator") {
        let c_obj = coord.as_object().ok_or_else(|| {
            PolicyError::Validation("$.coordinator: must be a mapping".to_string())
        })?;
        if let Some(v) = c_obj.get("aggregator") {
            let s = v.as_str().unwrap_or("");
            if !matches!(s, "sum" | "mean" | "max" | "weighted_sum") {
                return Err(PolicyError::Validation(format!(
                    "$.coordinator.aggregator: must be one of sum|mean|max|weighted_sum (got {})",
                    v
                )));
            }
        }
        if let (Some(esc), Some(rel)) = (
            c_obj.get("escalation_threshold").and_then(extract_f64),
            c_obj.get("release_threshold").and_then(extract_f64),
        ) {
            if rel <= esc {
                return Err(PolicyError::Validation(format!(
                    "$.coordinator.release_threshold: must exceed escalation_threshold ({} <= {})",
                    rel, esc
                )));
            }
        }
    }

    if let Some(consent) = map.get("consent") {
        let c_obj = consent.as_object().ok_or_else(|| {
            PolicyError::Validation("$.consent: must be a mapping".to_string())
        })?;
        if let Some(scopes) = c_obj.get("required_scopes") {
            let arr = scopes.as_array().ok_or_else(|| {
                PolicyError::Validation("$.consent.required_scopes: expected list".to_string())
            })?;
            for (i, s) in arr.iter().enumerate() {
                let scope_str = s.as_str().unwrap_or("");
                if !validate_scope_string(scope_str) {
                    return Err(PolicyError::Validation(format!(
                        "$.consent.required_scopes[{}]: {} is not a valid scope",
                        i, s
                    )));
                }
            }
        }
    }

    Ok(())
}

/// Build a [`Policy`] from a parsed document. Validates first.
pub fn build(doc: &Value) -> Result<Policy, PolicyError> {
    validate(doc)?;
    let map = doc.as_object().expect("validated as object");

    let mut pressure = PressureConfig::default();
    if let Some(p) = map.get("pressure").and_then(Value::as_object) {
        if let Some(v) = p.get("escalation_threshold").and_then(extract_f64) {
            pressure.escalation_threshold = v;
        }
        if let Some(v) = p.get("release_threshold").and_then(extract_f64) {
            pressure.release_threshold = v;
        }
        if let Some(v) = p.get("dissipation_per_step").and_then(extract_f64) {
            pressure.dissipation_per_step = v;
        }
        if let Some(v) = p.get("dissipation_per_second").and_then(extract_f64) {
            pressure.dissipation_per_second = v;
        }
        if let Some(v) = p.get("token_coefficient").and_then(extract_f64) {
            pressure.token_coefficient = v;
        }
        if let Some(v) = p.get("tool_coefficient").and_then(extract_f64) {
            pressure.tool_coefficient = v;
        }
        if let Some(v) = p.get("depth_coefficient").and_then(extract_f64) {
            pressure.depth_coefficient = v;
        }
        if let Some(v) = p.get("post_release_lock").and_then(Value::as_bool) {
            pressure.post_release_lock = v;
        }
    }
    pressure
        .validate()
        .map_err(|e| PolicyError::Validation(format!("$.pressure: {}", e)))?;

    let mut coord = CoordinatorConfig::default();
    let mut aggregator: Box<dyn Aggregator> = Box::new(SumAggregator);
    if let Some(c) = map.get("coordinator").and_then(Value::as_object) {
        if let Some(v) = c.get("escalation_threshold").and_then(extract_f64) {
            coord.escalation_threshold = v;
        }
        if let Some(v) = c.get("release_threshold").and_then(extract_f64) {
            coord.release_threshold = v;
        }
        if let Some(v) = c.get("notify_cooldown_seconds").and_then(extract_f64) {
            coord.notify_cooldown_seconds = v;
        }
        aggregator = build_aggregator(c);
    }

    let mut consent_p = ConsentPolicy::default();
    if let Some(c) = map.get("consent").and_then(Value::as_object) {
        if let Some(v) = c.get("issuer").and_then(Value::as_str) {
            consent_p.issuer = Some(v.to_string());
        }
        if let Some(v) = c.get("default_ttl_seconds").and_then(extract_f64) {
            consent_p.default_ttl_seconds = v;
        }
        if let Some(arr) = c.get("required_scopes").and_then(Value::as_array) {
            consent_p.required_scopes = arr
                .iter()
                .filter_map(|s| s.as_str().map(String::from))
                .collect();
        }
        if let Some(arr) = c.get("allowed_algorithms").and_then(Value::as_array) {
            consent_p.allowed_algorithms = arr
                .iter()
                .filter_map(|s| s.as_str().map(String::from))
                .collect();
        }
    }

    let metadata = map
        .get("metadata")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();

    Ok(Policy {
        version: "1".to_string(),
        pressure,
        coordinator: coord,
        consent: consent_p,
        aggregator,
        metadata,
    })
}

fn build_aggregator(coord: &serde_json::Map<String, Value>) -> Box<dyn Aggregator> {
    match coord.get("aggregator").and_then(Value::as_str) {
        Some("mean") => Box::new(MeanAggregator),
        Some("max") => Box::new(MaxAggregator),
        Some("weighted_sum") => {
            let mut weights = BTreeMap::new();
            if let Some(w) = coord.get("weights").and_then(Value::as_object) {
                for (k, v) in w {
                    if let Some(f) = extract_f64(v) {
                        weights.insert(k.clone(), f);
                    }
                }
            }
            let default_weight = coord
                .get("default_weight")
                .and_then(extract_f64)
                .unwrap_or(1.0);
            Box::new(WeightedSumAggregator {
                weights,
                default_weight,
            })
        }
        _ => Box::new(SumAggregator),
    }
}

/// Parse JSON-encoded policy bytes.
pub fn parse_json(data: &[u8]) -> Result<Policy, PolicyError> {
    let doc: Value = serde_json::from_slice(data)?;
    build(&doc)
}

/// Parse YAML-encoded policy bytes.
pub fn parse_yaml(data: &[u8]) -> Result<Policy, PolicyError> {
    let doc: Value = serde_yaml::from_slice(data)?;
    build(&doc)
}

/// Load a policy file, dispatching by extension.
pub fn load(path: impl AsRef<Path>) -> Result<Policy, PolicyError> {
    let path = path.as_ref();
    let data = std::fs::read(path)?;
    let ext = path
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_lowercase();
    match ext.as_str() {
        "json" => parse_json(&data),
        "yaml" | "yml" => parse_yaml(&data),
        other => Err(PolicyError::UnsupportedExtension(format!(".{}", other))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn build_minimal_policy() {
        let p = build(&json!({"version": "1"})).unwrap();
        assert_eq!(p.version, "1");
        assert_eq!(p.aggregator.name(), AggregatorKind::Sum);
    }

    #[test]
    fn build_overrides_defaults() {
        let p = build(&json!({
            "version": "1",
            "pressure": {
                "escalation_threshold": 0.7,
                "release_threshold": 0.85
            },
            "coordinator": {"aggregator": "max"}
        }))
        .unwrap();
        assert_eq!(p.pressure.escalation_threshold, 0.7);
        assert_eq!(p.aggregator.name(), AggregatorKind::Max);
    }

    #[test]
    fn build_rejects_missing_version() {
        assert!(matches!(
            build(&json!({})),
            Err(PolicyError::Validation(_))
        ));
    }

    #[test]
    fn build_rejects_bad_version() {
        assert!(matches!(
            build(&json!({"version": "2"})),
            Err(PolicyError::Validation(_))
        ));
    }

    #[test]
    fn build_rejects_release_below_escalation() {
        assert!(matches!(
            build(&json!({
                "version": "1",
                "pressure": {"escalation_threshold": 0.9, "release_threshold": 0.5}
            })),
            Err(PolicyError::Validation(_))
        ));
    }

    #[test]
    fn parse_yaml_works() {
        let yaml = b"version: \"1\"\npressure:\n  escalation_threshold: 0.8\n  release_threshold: 0.9\ncoordinator:\n  aggregator: mean\n";
        let p = parse_yaml(yaml).unwrap();
        assert_eq!(p.pressure.escalation_threshold, 0.8);
        assert_eq!(p.aggregator.name(), AggregatorKind::Mean);
    }

    #[test]
    fn sum_aggregator() {
        let mut m = BTreeMap::new();
        m.insert("a".to_string(), 0.3);
        m.insert("b".to_string(), 0.5);
        assert!((SumAggregator.aggregate(&m) - 0.8).abs() < 1e-9);
    }

    #[test]
    fn weighted_sum_aggregator() {
        let mut w = BTreeMap::new();
        w.insert("important".to_string(), 2.0);
        let agg = WeightedSumAggregator {
            weights: w,
            default_weight: 1.0,
        };
        let mut m = BTreeMap::new();
        m.insert("important".to_string(), 0.5);
        m.insert("normal".to_string(), 0.3);
        assert!((agg.aggregate(&m) - 1.3).abs() < 1e-9);
    }
}

//! Wire-format types shared with the other reference SDKs.

use serde::{Deserialize, Serialize};

/// The engine's high-level lifecycle state. Wire-format strings —
/// these MUST match the Python, Node, and Go SDKs exactly.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Lifecycle {
    Init,
    Running,
    Escalated,
    Released,
    Locked,
}

impl Lifecycle {
    pub fn as_str(&self) -> &'static str {
        match self {
            Lifecycle::Init => "init",
            Lifecycle::Running => "running",
            Lifecycle::Escalated => "escalated",
            Lifecycle::Released => "released",
            Lifecycle::Locked => "locked",
        }
    }
}

/// Result of a single `step` call. Lowercase wire-format strings.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StepOutcome {
    Ok,
    Escalated,
    Released,
    Locked,
}

impl StepOutcome {
    pub fn as_str(&self) -> &'static str {
        match self {
            StepOutcome::Ok => "ok",
            StepOutcome::Escalated => "escalated",
            StepOutcome::Released => "released",
            StepOutcome::Locked => "locked",
        }
    }
}

/// A clock function returning fractional seconds. Tests use scripted
/// clocks for deterministic evaluation.
pub type Clock = std::sync::Arc<dyn Fn() -> f64 + Send + Sync>;

/// Build a wallclock-based [`Clock`] using `chrono::Utc::now`.
pub fn wallclock() -> Clock {
    use chrono::Utc;
    std::sync::Arc::new(|| {
        let now = Utc::now();
        now.timestamp() as f64 + (now.timestamp_subsec_nanos() as f64 / 1e9)
    })
}

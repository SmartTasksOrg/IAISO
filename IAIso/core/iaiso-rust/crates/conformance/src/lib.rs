//! IAIso conformance runner.
//!
//! Loads the spec vectors and runs them against this implementation.

use iaiso_audit::{MemorySink, NullSink, Sink};
use iaiso_core::{Clock, EngineOptions, Lifecycle, PressureConfig, PressureEngine, StepInput};
use serde::Deserialize;
use serde_json::Value;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

/// Absolute tolerance for floating-point comparisons.
pub const TOLERANCE: f64 = 1e-9;

/// Result of running one vector.
#[derive(Debug, Clone)]
pub struct VectorResult {
    pub section: String,
    pub name: String,
    pub passed: bool,
    pub message: String,
}

/// Aggregate results grouped by section.
#[derive(Debug, Default)]
pub struct SectionResults {
    pub pressure: Vec<VectorResult>,
    pub consent: Vec<VectorResult>,
    pub events: Vec<VectorResult>,
    pub policy: Vec<VectorResult>,
}

impl SectionResults {
    pub fn count_passed(&self) -> (usize, usize) {
        let mut p = 0;
        let mut t = 0;
        for v in [&self.pressure, &self.consent, &self.events, &self.policy] {
            for r in v {
                t += 1;
                if r.passed {
                    p += 1;
                }
            }
        }
        (p, t)
    }
}

fn float_close(a: f64, b: f64) -> bool {
    if a.is_nan() || b.is_nan() {
        return a == b;
    }
    (a - b).abs() <= TOLERANCE
}

fn scripted_clock(seq: Vec<f64>) -> Clock {
    let idx = Arc::new(AtomicUsize::new(0));
    let seq = Arc::new(seq);
    Arc::new(move || {
        let i = idx.fetch_add(1, Ordering::SeqCst);
        if i < seq.len() {
            seq[i]
        } else {
            *seq.last().unwrap_or(&0.0)
        }
    })
}

fn config_from_value(raw: &Value) -> PressureConfig {
    let mut cfg = PressureConfig::default();
    if let Some(obj) = raw.as_object() {
        if let Some(v) = obj.get("escalation_threshold").and_then(Value::as_f64) {
            cfg.escalation_threshold = v;
        }
        if let Some(v) = obj.get("release_threshold").and_then(Value::as_f64) {
            cfg.release_threshold = v;
        }
        if let Some(v) = obj.get("dissipation_per_step").and_then(Value::as_f64) {
            cfg.dissipation_per_step = v;
        }
        if let Some(v) = obj.get("dissipation_per_second").and_then(Value::as_f64) {
            cfg.dissipation_per_second = v;
        }
        if let Some(v) = obj.get("token_coefficient").and_then(Value::as_f64) {
            cfg.token_coefficient = v;
        }
        if let Some(v) = obj.get("tool_coefficient").and_then(Value::as_f64) {
            cfg.tool_coefficient = v;
        }
        if let Some(v) = obj.get("depth_coefficient").and_then(Value::as_f64) {
            cfg.depth_coefficient = v;
        }
        if let Some(v) = obj.get("post_release_lock").and_then(Value::as_bool) {
            cfg.post_release_lock = v;
        }
    }
    cfg
}

#[derive(Debug, Deserialize)]
struct PressureStep {
    #[serde(default)]
    tokens: u64,
    #[serde(default)]
    tool_calls: u64,
    #[serde(default)]
    depth: u64,
    #[serde(default)]
    tag: Option<String>,
    #[serde(default)]
    reset: bool,
}

#[derive(Debug, Deserialize)]
struct PressureExpectedStep {
    step: u64,
    #[serde(default)]
    delta: f64,
    #[serde(default)]
    decay: f64,
    pressure: f64,
    lifecycle: String,
    outcome: String,
}

#[derive(Debug, Deserialize)]
struct PressureExpectedInitial {
    pressure: f64,
    step: u64,
    lifecycle: String,
    last_step_at: f64,
}

#[derive(Debug, Deserialize)]
struct PressureVector {
    name: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    config: serde_json::Value,
    #[serde(default)]
    clock: Vec<f64>,
    #[serde(default)]
    steps: Vec<PressureStep>,
    #[serde(default)]
    expected_initial: Option<PressureExpectedInitial>,
    #[serde(default)]
    expected_steps: Vec<PressureExpectedStep>,
    #[serde(default)]
    expect_config_error: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PressureFile {
    vectors: Vec<PressureVector>,
}

/// Run pressure vectors.
pub fn run_pressure(spec_root: &Path) -> Result<Vec<VectorResult>, String> {
    let path = spec_root.join("pressure").join("vectors.json");
    let data = std::fs::read(&path).map_err(|e| format!("read {}: {}", path.display(), e))?;
    let file: PressureFile =
        serde_json::from_slice(&data).map_err(|e| format!("parse {}: {}", path.display(), e))?;

    let mut results = Vec::with_capacity(file.vectors.len());
    for v in file.vectors {
        results.push(run_one_pressure(v));
    }
    Ok(results)
}

fn run_one_pressure(v: PressureVector) -> VectorResult {
    let mut r = VectorResult {
        section: "pressure".to_string(),
        name: v.name.clone(),
        passed: false,
        message: String::new(),
    };
    let cfg = config_from_value(&v.config);
    let clock = scripted_clock(v.clock.clone());

    let engine_res = PressureEngine::new(
        cfg,
        EngineOptions {
            execution_id: format!("vec-{}", v.name),
            audit_sink: Arc::new(NullSink),
            clock: clock.clone(),
            timestamp_clock: clock,
        },
    );

    if let Some(expected_err) = &v.expect_config_error {
        match engine_res {
            Ok(_) => {
                r.message = format!("expected config error containing {:?}, got Ok", expected_err);
            }
            Err(e) => {
                let msg = e.to_string();
                if !msg.contains(expected_err) {
                    r.message = format!(
                        "expected config error containing {:?}, got {:?}",
                        expected_err, msg
                    );
                } else {
                    r.passed = true;
                }
            }
        }
        return r;
    }

    let engine = match engine_res {
        Ok(e) => e,
        Err(e) => {
            r.message = format!("engine construction failed: {}", e);
            return r;
        }
    };

    if let Some(init) = &v.expected_initial {
        let snap = engine.snapshot();
        if !float_close(snap.pressure, init.pressure) {
            r.message = format!("initial pressure: got {}, want {}", snap.pressure, init.pressure);
            return r;
        }
        if snap.step != init.step {
            r.message = format!("initial step: got {}, want {}", snap.step, init.step);
            return r;
        }
        if snap.lifecycle.as_str() != init.lifecycle {
            r.message = format!(
                "initial lifecycle: got {}, want {}",
                snap.lifecycle.as_str(),
                init.lifecycle
            );
            return r;
        }
        if !float_close(snap.last_step_at, init.last_step_at) {
            r.message = format!(
                "initial last_step_at: got {}, want {}",
                snap.last_step_at, init.last_step_at
            );
            return r;
        }
    }

    for (i, step) in v.steps.iter().enumerate() {
        let outcome = if step.reset {
            engine.reset();
            iaiso_core::StepOutcome::Ok
        } else {
            engine.step(StepInput {
                tokens: step.tokens,
                tool_calls: step.tool_calls,
                depth: step.depth,
                tag: step.tag.clone(),
            })
        };
        if i >= v.expected_steps.len() {
            r.message = format!("step {}: produced output but no expected entry", i);
            return r;
        }
        let exp = &v.expected_steps[i];
        if outcome.as_str() != exp.outcome {
            r.message = format!(
                "step {}: outcome got {}, want {}",
                i,
                outcome.as_str(),
                exp.outcome
            );
            return r;
        }
        let snap = engine.snapshot();
        if !float_close(snap.pressure, exp.pressure) {
            r.message = format!(
                "step {}: pressure got {}, want {}",
                i, snap.pressure, exp.pressure
            );
            return r;
        }
        if snap.step != exp.step {
            r.message = format!("step {}: step got {}, want {}", i, snap.step, exp.step);
            return r;
        }
        if snap.lifecycle.as_str() != exp.lifecycle {
            r.message = format!(
                "step {}: lifecycle got {}, want {}",
                i,
                snap.lifecycle.as_str(),
                exp.lifecycle
            );
            return r;
        }
    }
    r.passed = true;
    r
}

mod consent_runner;
mod events_runner;
mod policy_runner;

pub use consent_runner::run_consent;
pub use events_runner::run_events;
pub use policy_runner::run_policy;

/// Run every section.
pub fn run_all(spec_root: &Path) -> Result<SectionResults, String> {
    Ok(SectionResults {
        pressure: run_pressure(spec_root)?,
        consent: run_consent(spec_root)?,
        events: run_events(spec_root)?,
        policy: run_policy(spec_root)?,
    })
}

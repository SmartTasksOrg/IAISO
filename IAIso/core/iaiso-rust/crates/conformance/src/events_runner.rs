use crate::{config_from_value, scripted_clock, VectorResult};
use iaiso_audit::MemorySink;
use iaiso_core::{EngineOptions, PressureEngine, StepInput};
use serde::Deserialize;
use serde_json::Value;
use std::path::Path;
use std::sync::Arc;

#[derive(Debug, Deserialize)]
struct EventsStep {
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
struct ExpectedEvent {
    #[serde(default)]
    schema_version: Option<String>,
    #[serde(default)]
    execution_id: Option<String>,
    kind: String,
    #[serde(default)]
    data: Option<Value>,
}

#[derive(Debug, Deserialize)]
struct EventsVector {
    name: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    config: Value,
    #[serde(default)]
    clock: Vec<f64>,
    #[serde(default)]
    steps: Vec<EventsStep>,
    #[serde(default)]
    reset_after_step: Option<usize>,
    #[serde(default)]
    clock_after_reset: Option<f64>,
    execution_id: String,
    expected_events: Vec<ExpectedEvent>,
}

#[derive(Debug, Deserialize)]
struct EventsFile {
    vectors: Vec<EventsVector>,
}

pub fn run_events(spec_root: &Path) -> Result<Vec<VectorResult>, String> {
    let path = spec_root.join("events").join("vectors.json");
    let data = std::fs::read(&path).map_err(|e| format!("read {}: {}", path.display(), e))?;
    let file: EventsFile =
        serde_json::from_slice(&data).map_err(|e| format!("parse {}: {}", path.display(), e))?;

    let mut results = Vec::with_capacity(file.vectors.len());
    for v in file.vectors {
        results.push(run_one_events(v));
    }
    Ok(results)
}

fn run_one_events(v: EventsVector) -> VectorResult {
    let mut r = VectorResult {
        section: "events".to_string(),
        name: v.name.clone(),
        passed: false,
        message: String::new(),
    };
    let cfg = config_from_value(&v.config);
    let clock = scripted_clock(v.clock.clone());
    let sink = Arc::new(MemorySink::new());

    let engine = match PressureEngine::new(
        cfg,
        EngineOptions {
            execution_id: v.execution_id.clone(),
            audit_sink: sink.clone(),
            clock: clock.clone(),
            timestamp_clock: clock,
        },
    ) {
        Ok(e) => e,
        Err(e) => {
            r.message = format!("engine construction failed: {}", e);
            return r;
        }
    };

    for (i, step) in v.steps.iter().enumerate() {
        if step.reset {
            engine.reset();
        } else {
            engine.step(StepInput {
                tokens: step.tokens,
                tool_calls: step.tool_calls,
                depth: step.depth,
                tag: step.tag.clone(),
            });
        }
        // 1-based: reset_after_step = N triggers after running step N
        if let Some(after) = v.reset_after_step {
            if i + 1 == after {
                engine.reset();
            }
        }
    }

    let got = sink.events();
    if got.len() != v.expected_events.len() {
        r.message = format!(
            "event count: got {}, want {}",
            got.len(),
            v.expected_events.len()
        );
        return r;
    }

    for (i, exp) in v.expected_events.iter().enumerate() {
        let actual = &got[i];
        if let Some(sv) = &exp.schema_version {
            if !sv.is_empty() && actual.schema_version != *sv {
                r.message = format!(
                    "event {} schema_version: got {}, want {}",
                    i, actual.schema_version, sv
                );
                return r;
            }
        }
        if let Some(eid) = &exp.execution_id {
            if !eid.is_empty() && actual.execution_id != *eid {
                r.message = format!(
                    "event {} execution_id: got {}, want {}",
                    i, actual.execution_id, eid
                );
                return r;
            }
        }
        if actual.kind != exp.kind {
            r.message = format!("event {} kind: got {}, want {}", i, actual.kind, exp.kind);
            return r;
        }
        if let Some(want_data) = &exp.data {
            if !data_equal(&actual.data, want_data) {
                r.message = format!(
                    "event {} data mismatch: got {:?}, want {:?}",
                    i, actual.data, want_data
                );
                return r;
            }
        }
    }
    r.passed = true;
    r
}

/// Loose-equality comparison: missing keys in actual that map to nil in
/// expected are treated as equivalent; numbers compared with TOLERANCE.
fn data_equal(actual: &std::collections::BTreeMap<String, Value>, want: &Value) -> bool {
    let want_obj = match want.as_object() {
        Some(o) => o,
        None => return false,
    };
    for (k, w) in want_obj {
        let a = actual.get(k).cloned().unwrap_or(Value::Null);
        if !value_equal(&a, w) {
            return false;
        }
    }
    true
}

fn value_equal(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Null, Value::Null) => true,
        (Value::Bool(x), Value::Bool(y)) => x == y,
        (Value::String(x), Value::String(y)) => x == y,
        (Value::Number(x), Value::Number(y)) => match (x.as_f64(), y.as_f64()) {
            (Some(xf), Some(yf)) => (xf - yf).abs() <= crate::TOLERANCE,
            _ => x == y,
        },
        (Value::Array(x), Value::Array(y)) => {
            x.len() == y.len() && x.iter().zip(y).all(|(xv, yv)| value_equal(xv, yv))
        }
        (Value::Object(x), Value::Object(y)) => {
            x.len() == y.len()
                && x.iter()
                    .all(|(k, v)| y.get(k).map_or(false, |w| value_equal(v, w)))
        }
        _ => false,
    }
}

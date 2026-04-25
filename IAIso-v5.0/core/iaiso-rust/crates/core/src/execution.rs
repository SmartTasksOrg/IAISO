//! High-level execution facade. Composes a [`PressureEngine`] with an
//! attached consent scope and audit sink.

use crate::config::{ConfigError, PressureConfig};
use crate::engine::{EngineOptions, PressureEngine, PressureSnapshot, StepInput};
use crate::types::{Clock, Lifecycle, StepOutcome};
use iaiso_audit::{Event, NullSink, Sink};
use parking_lot::Mutex;
use serde_json::json;
use std::collections::BTreeMap;
use std::sync::Arc;
use thiserror::Error;

/// Errors produced by [`BoundedExecution`].
#[derive(Debug, Error)]
pub enum ExecutionError {
    #[error("execution is locked; call reset() before continuing")]
    Locked,
    #[error("config error: {0}")]
    Config(#[from] ConfigError),
}

/// Options for [`BoundedExecution::start`] / [`BoundedExecution::run`].
pub struct BoundedExecutionOptions {
    /// If empty, a random execution id is generated.
    pub execution_id: String,
    pub config: PressureConfig,
    pub audit_sink: Arc<dyn Sink>,
    pub clock: Option<Clock>,
    pub timestamp_clock: Option<Clock>,
}

impl Default for BoundedExecutionOptions {
    fn default() -> Self {
        Self {
            execution_id: String::new(),
            config: PressureConfig::default(),
            audit_sink: Arc::new(NullSink),
            clock: None,
            timestamp_clock: None,
        }
    }
}

/// A bounded execution. Wraps a [`PressureEngine`] with execution-level
/// audit emissions and ergonomic helpers.
pub struct BoundedExecution {
    engine: PressureEngine,
    audit_sink: Arc<dyn Sink>,
    timestamp_clock: Clock,
    closed: Mutex<bool>,
}

impl BoundedExecution {
    /// Construct a [`BoundedExecution`]. Caller is responsible for
    /// invoking [`BoundedExecution::close`] (typically via the
    /// [`BoundedExecution::run`] facade or RAII via `Drop`).
    pub fn start(opts: BoundedExecutionOptions) -> Result<Self, ExecutionError> {
        let exec_id = if opts.execution_id.is_empty() {
            format!("exec-{}", random_id())
        } else {
            opts.execution_id
        };
        let clk = opts.clock.unwrap_or_else(crate::types::wallclock);
        let ts_clk = opts.timestamp_clock.unwrap_or_else(|| clk.clone());

        let engine = PressureEngine::new(
            opts.config,
            EngineOptions {
                execution_id: exec_id,
                audit_sink: opts.audit_sink.clone(),
                clock: clk,
                timestamp_clock: ts_clk.clone(),
            },
        )?;

        Ok(Self {
            engine,
            audit_sink: opts.audit_sink,
            timestamp_clock: ts_clk,
            closed: Mutex::new(false),
        })
    }

    /// Run a closure inside a bounded execution. Guarantees `close` is
    /// called even if the closure returns early.
    pub fn run<F, R>(opts: BoundedExecutionOptions, f: F) -> Result<R, ExecutionError>
    where
        F: FnOnce(&BoundedExecution) -> Result<R, ExecutionError>,
    {
        let exec = Self::start(opts)?;
        let result = f(&exec);
        exec.close(result.is_err());
        result
    }

    pub fn engine(&self) -> &PressureEngine {
        &self.engine
    }

    pub fn snapshot(&self) -> PressureSnapshot {
        self.engine.snapshot()
    }

    /// Account for tokens with an optional tag.
    pub fn record_tokens(&self, tokens: u64, tag: Option<&str>) -> Result<StepOutcome, ExecutionError> {
        self.account(StepInput {
            tokens,
            tag: tag.map(|s| s.to_string()),
            ..Default::default()
        })
    }

    /// Account for a single tool invocation.
    pub fn record_tool_call(&self, name: &str, tokens: u64) -> Result<StepOutcome, ExecutionError> {
        self.account(StepInput {
            tokens,
            tool_calls: 1,
            tag: Some(name.to_string()),
            ..Default::default()
        })
    }

    /// General step accounting.
    pub fn record_step(&self, work: StepInput) -> Result<StepOutcome, ExecutionError> {
        self.account(work)
    }

    fn account(&self, work: StepInput) -> Result<StepOutcome, ExecutionError> {
        let outcome = self.engine.step(work);
        if outcome == StepOutcome::Locked {
            return Err(ExecutionError::Locked);
        }
        Ok(outcome)
    }

    /// Pre-check the engine state without advancing it.
    pub fn check(&self) -> StepOutcome {
        match self.engine.lifecycle() {
            Lifecycle::Locked => StepOutcome::Locked,
            Lifecycle::Escalated => StepOutcome::Escalated,
            _ => StepOutcome::Ok,
        }
    }

    pub fn reset(&self) -> PressureSnapshot {
        self.engine.reset()
    }

    /// Emit `execution.closed`. Idempotent.
    pub fn close(&self, errored: bool) {
        let mut closed = self.closed.lock();
        if *closed {
            return;
        }
        *closed = true;
        let snap = self.engine.snapshot();
        let mut data = BTreeMap::new();
        data.insert("final_pressure".to_string(), json!(snap.pressure));
        data.insert("final_lifecycle".to_string(), json!(snap.lifecycle.as_str()));
        data.insert(
            "exception".to_string(),
            if errored {
                json!("error")
            } else {
                serde_json::Value::Null
            },
        );
        let event = Event::new(
            self.engine.execution_id().to_string(),
            "execution.closed",
            (self.timestamp_clock)(),
            data,
        );
        self.audit_sink.emit(&event);
    }
}

impl Drop for BoundedExecution {
    fn drop(&mut self) {
        // Best-effort close on drop. If user already called close()
        // this is a no-op; otherwise it ensures execution.closed is
        // emitted even when the user forgets.
        let already = *self.closed.lock();
        if !already {
            self.close(false);
        }
    }
}

fn random_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.subsec_nanos())
        .unwrap_or(0);
    let pid = std::process::id();
    format!("{:08x}{:04x}", nanos, pid & 0xffff)
}

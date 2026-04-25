//! The pressure engine — the runtime layer of IAIso.

use crate::config::{ConfigError, PressureConfig};
use crate::types::{Clock, Lifecycle, StepOutcome};
use iaiso_audit::{Event, NullSink, Sink};
use parking_lot::Mutex;
use serde_json::json;
use std::collections::BTreeMap;
use std::sync::Arc;

/// Work unit accounted for in a single `step` call.
#[derive(Debug, Clone, Default)]
pub struct StepInput {
    pub tokens: u64,
    pub tool_calls: u64,
    pub depth: u64,
    pub tag: Option<String>,
}

/// Read-only snapshot of engine state.
#[derive(Debug, Clone, Copy)]
pub struct PressureSnapshot {
    pub pressure: f64,
    pub step: u64,
    pub lifecycle: Lifecycle,
    pub last_delta: f64,
    pub last_step_at: f64,
}

/// Options for [`PressureEngine::new`].
pub struct EngineOptions {
    pub execution_id: String,
    pub audit_sink: Arc<dyn Sink>,
    pub clock: Clock,
    pub timestamp_clock: Clock,
}

impl EngineOptions {
    pub fn new(execution_id: impl Into<String>) -> Self {
        let clk = crate::types::wallclock();
        Self {
            execution_id: execution_id.into(),
            audit_sink: Arc::new(NullSink),
            clock: clk.clone(),
            timestamp_clock: clk,
        }
    }
}

struct EngineState {
    pressure: f64,
    step: u64,
    lifecycle: Lifecycle,
    last_delta: f64,
    last_step_at: f64,
}

/// The pressure engine. Thread-safe — `Step()` may be called from
/// multiple threads, though semantically each execution should be
/// driven by a single thread.
pub struct PressureEngine {
    cfg: PressureConfig,
    execution_id: String,
    audit: Arc<dyn Sink>,
    clock: Clock,
    timestamp_clock: Clock,
    state: Mutex<EngineState>,
}

impl PressureEngine {
    /// Construct an engine. Validates the config; emits `engine.init`.
    pub fn new(cfg: PressureConfig, opts: EngineOptions) -> Result<Self, ConfigError> {
        cfg.validate()?;
        let now = (opts.clock)();
        let engine = Self {
            cfg,
            execution_id: opts.execution_id,
            audit: opts.audit_sink,
            clock: opts.clock,
            timestamp_clock: opts.timestamp_clock,
            state: Mutex::new(EngineState {
                pressure: 0.0,
                step: 0,
                lifecycle: Lifecycle::Init,
                last_delta: 0.0,
                last_step_at: now,
            }),
        };
        engine.emit("engine.init", {
            let mut m = BTreeMap::new();
            m.insert("pressure".to_string(), json!(0.0));
            m
        });
        Ok(engine)
    }

    pub fn config(&self) -> &PressureConfig {
        &self.cfg
    }
    pub fn execution_id(&self) -> &str {
        &self.execution_id
    }
    pub fn pressure(&self) -> f64 {
        self.state.lock().pressure
    }
    pub fn lifecycle(&self) -> Lifecycle {
        self.state.lock().lifecycle
    }

    pub fn snapshot(&self) -> PressureSnapshot {
        let s = self.state.lock();
        PressureSnapshot {
            pressure: s.pressure,
            step: s.step,
            lifecycle: s.lifecycle,
            last_delta: s.last_delta,
            last_step_at: s.last_step_at,
        }
    }

    /// Account for a unit of work and advance the engine.
    pub fn step(&self, work: StepInput) -> StepOutcome {
        let mut s = self.state.lock();
        if s.lifecycle == Lifecycle::Locked {
            // Emit step.rejected without holding state lock for emit
            drop(s);
            self.emit("engine.step.rejected", {
                let mut m = BTreeMap::new();
                m.insert("reason".to_string(), json!("locked"));
                m.insert("requested_tokens".to_string(), json!(work.tokens));
                m.insert("requested_tools".to_string(), json!(work.tool_calls));
                m
            });
            return StepOutcome::Locked;
        }

        let now = (self.clock)();
        let elapsed = (now - s.last_step_at).max(0.0);

        let delta = (work.tokens as f64 / 1000.0) * self.cfg.token_coefficient
            + (work.tool_calls as f64) * self.cfg.tool_coefficient
            + (work.depth as f64) * self.cfg.depth_coefficient;
        let decay = self.cfg.dissipation_per_step + elapsed * self.cfg.dissipation_per_second;

        let new_pressure = (s.pressure + delta - decay).clamp(0.0, 1.0);
        s.pressure = new_pressure;
        s.step += 1;
        s.last_delta = delta - decay;
        s.last_step_at = now;
        s.lifecycle = Lifecycle::Running;

        let step_data = {
            let mut m = BTreeMap::new();
            m.insert("step".to_string(), json!(s.step));
            m.insert("pressure".to_string(), json!(s.pressure));
            m.insert("delta".to_string(), json!(delta));
            m.insert("decay".to_string(), json!(decay));
            m.insert("tokens".to_string(), json!(work.tokens));
            m.insert("tool_calls".to_string(), json!(work.tool_calls));
            m.insert("depth".to_string(), json!(work.depth));
            m.insert(
                "tag".to_string(),
                match &work.tag {
                    Some(t) => json!(t),
                    None => serde_json::Value::Null,
                },
            );
            m
        };

        let pressure_now = s.pressure;
        let release_threshold = self.cfg.release_threshold;
        let escalation_threshold = self.cfg.escalation_threshold;
        let post_release_lock = self.cfg.post_release_lock;
        drop(s); // release before emitting

        self.emit("engine.step", step_data);

        if pressure_now >= release_threshold {
            // release path
            self.emit("engine.release", {
                let mut m = BTreeMap::new();
                m.insert("pressure".to_string(), json!(pressure_now));
                m.insert("threshold".to_string(), json!(release_threshold));
                m
            });
            let mut s = self.state.lock();
            s.pressure = 0.0;
            if post_release_lock {
                s.lifecycle = Lifecycle::Locked;
                drop(s);
                self.emit("engine.locked", {
                    let mut m = BTreeMap::new();
                    m.insert("reason".to_string(), json!("post_release_lock"));
                    m
                });
            } else {
                s.lifecycle = Lifecycle::Running;
            }
            StepOutcome::Released
        } else if pressure_now >= escalation_threshold {
            {
                let mut s = self.state.lock();
                s.lifecycle = Lifecycle::Escalated;
            }
            self.emit("engine.escalation", {
                let mut m = BTreeMap::new();
                m.insert("pressure".to_string(), json!(pressure_now));
                m.insert("threshold".to_string(), json!(escalation_threshold));
                m
            });
            StepOutcome::Escalated
        } else {
            StepOutcome::Ok
        }
    }

    /// Reset the engine — clears pressure, returns lifecycle to Init,
    /// emits `engine.reset`.
    pub fn reset(&self) -> PressureSnapshot {
        let now = (self.clock)();
        {
            let mut s = self.state.lock();
            s.pressure = 0.0;
            s.step = 0;
            s.last_delta = 0.0;
            s.last_step_at = now;
            s.lifecycle = Lifecycle::Init;
        }
        self.emit("engine.reset", {
            let mut m = BTreeMap::new();
            m.insert("pressure".to_string(), json!(0.0));
            m
        });
        self.snapshot()
    }

    fn emit(&self, kind: &str, data: BTreeMap<String, serde_json::Value>) {
        let event = Event::new(self.execution_id.clone(), kind, (self.timestamp_clock)(), data);
        self.audit.emit(&event);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use iaiso_audit::MemorySink;

    fn scripted(seq: Vec<f64>) -> Clock {
        let idx = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
        let seq = std::sync::Arc::new(seq);
        Arc::new(move || {
            let i = idx.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            if i < seq.len() {
                seq[i]
            } else {
                *seq.last().unwrap_or(&0.0)
            }
        })
    }

    #[test]
    fn step_accumulates_pressure() {
        let cfg = PressureConfig {
            dissipation_per_step: 0.0,
            ..PressureConfig::default()
        };
        let sink = Arc::new(MemorySink::new());
        let engine = PressureEngine::new(
            cfg,
            EngineOptions {
                execution_id: "t".to_string(),
                audit_sink: sink.clone(),
                clock: scripted(vec![0.0, 0.1, 0.2]),
                timestamp_clock: scripted(vec![0.0, 0.1, 0.2]),
            },
        )
        .unwrap();
        let out = engine.step(StepInput {
            tokens: 1000,
            ..Default::default()
        });
        assert_eq!(out, StepOutcome::Ok);
        assert!((engine.pressure() - 0.015).abs() < 1e-9);
    }

    #[test]
    fn step_escalates_at_threshold() {
        let cfg = PressureConfig {
            escalation_threshold: 0.5,
            release_threshold: 0.95,
            dissipation_per_step: 0.0,
            depth_coefficient: 0.6,
            ..PressureConfig::default()
        };
        let sink = Arc::new(MemorySink::new());
        let engine = PressureEngine::new(
            cfg,
            EngineOptions {
                execution_id: "t".to_string(),
                audit_sink: sink,
                clock: scripted(vec![0.0, 0.1]),
                timestamp_clock: scripted(vec![0.0, 0.1]),
            },
        )
        .unwrap();
        let out = engine.step(StepInput {
            depth: 1,
            ..Default::default()
        });
        assert_eq!(out, StepOutcome::Escalated);
        assert_eq!(engine.lifecycle(), Lifecycle::Escalated);
    }

    #[test]
    fn step_releases_and_locks() {
        let cfg = PressureConfig {
            escalation_threshold: 0.5,
            release_threshold: 0.75,
            dissipation_per_step: 0.0,
            depth_coefficient: 0.8,
            post_release_lock: true,
            ..PressureConfig::default()
        };
        let sink = Arc::new(MemorySink::new());
        let engine = PressureEngine::new(
            cfg,
            EngineOptions {
                execution_id: "t".to_string(),
                audit_sink: sink,
                clock: scripted(vec![0.0, 0.1]),
                timestamp_clock: scripted(vec![0.0, 0.1]),
            },
        )
        .unwrap();
        let out = engine.step(StepInput {
            depth: 1,
            ..Default::default()
        });
        assert_eq!(out, StepOutcome::Released);
        assert_eq!(engine.lifecycle(), Lifecycle::Locked);
        assert_eq!(engine.pressure(), 0.0);
    }

    #[test]
    fn locked_rejects_subsequent_steps() {
        let cfg = PressureConfig {
            escalation_threshold: 0.5,
            release_threshold: 0.75,
            dissipation_per_step: 0.0,
            depth_coefficient: 0.8,
            ..PressureConfig::default()
        };
        let sink = Arc::new(MemorySink::new());
        let engine = PressureEngine::new(
            cfg,
            EngineOptions {
                execution_id: "t".to_string(),
                audit_sink: sink.clone(),
                clock: scripted(vec![0.0, 0.1, 0.2]),
                timestamp_clock: scripted(vec![0.0, 0.1, 0.2]),
            },
        )
        .unwrap();
        engine.step(StepInput {
            depth: 1,
            ..Default::default()
        });
        let out = engine.step(StepInput {
            tokens: 100,
            ..Default::default()
        });
        assert_eq!(out, StepOutcome::Locked);
        assert!(sink.events().iter().any(|e| e.kind == "engine.step.rejected"));
    }

    #[test]
    fn reset_clears_state() {
        let cfg = PressureConfig {
            escalation_threshold: 0.5,
            release_threshold: 0.75,
            dissipation_per_step: 0.0,
            depth_coefficient: 0.8,
            ..PressureConfig::default()
        };
        let sink = Arc::new(MemorySink::new());
        let engine = PressureEngine::new(
            cfg,
            EngineOptions {
                execution_id: "t".to_string(),
                audit_sink: sink,
                clock: scripted(vec![0.0, 0.1, 0.2]),
                timestamp_clock: scripted(vec![0.0, 0.1, 0.2]),
            },
        )
        .unwrap();
        engine.step(StepInput {
            depth: 1,
            ..Default::default()
        });
        engine.reset();
        assert_eq!(engine.pressure(), 0.0);
        assert_eq!(engine.lifecycle(), Lifecycle::Init);
    }
}

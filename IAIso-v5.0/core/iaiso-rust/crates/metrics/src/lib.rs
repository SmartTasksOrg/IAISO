//! IAIso Prometheus metrics sink.
//!
//! Structurally typed — this crate doesn't depend on any specific
//! Prometheus client library. The official `prometheus` and
//! `prometheus-client` crates satisfy the trait contracts here with
//! thin adapters.
//!
//! # Exposed metrics
//!
//! - `iaiso_events_total{kind}` — counter
//! - `iaiso_escalations_total` — counter
//! - `iaiso_releases_total` — counter
//! - `iaiso_pressure{execution_id}` — gauge
//! - `iaiso_step_delta` — histogram
//!
//! # Suggested histogram buckets
//!
//! See [`SUGGESTED_HISTOGRAM_BUCKETS`].

use iaiso_audit::{Event, Sink};
use std::sync::Arc;

/// Suggested histogram buckets for `iaiso_step_delta`.
pub const SUGGESTED_HISTOGRAM_BUCKETS: &[f64] =
    &[0.0, 0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0];

/// A simple counter that supports `inc()`.
pub trait Counter: Send + Sync {
    fn inc(&self);
}

/// A labeled counter.
pub trait CounterVec: Send + Sync {
    fn with_label_values(&self, values: &[&str]) -> Box<dyn Counter>;
}

/// A simple gauge that supports `set()`.
pub trait Gauge: Send + Sync {
    fn set(&self, value: f64);
}

/// A labeled gauge.
pub trait GaugeVec: Send + Sync {
    fn with_label_values(&self, values: &[&str]) -> Box<dyn Gauge>;
}

/// A histogram that supports `observe()`.
pub trait Histogram: Send + Sync {
    fn observe(&self, value: f64);
}

/// A Prometheus-driven audit sink.
pub struct PrometheusSink {
    pub events: Option<Arc<dyn CounterVec>>,
    pub escalations: Option<Arc<dyn Counter>>,
    pub releases: Option<Arc<dyn Counter>>,
    pub pressure: Option<Arc<dyn GaugeVec>>,
    pub step_delta: Option<Arc<dyn Histogram>>,
}

impl Sink for PrometheusSink {
    fn emit(&self, event: &Event) {
        if let Some(events) = &self.events {
            events.with_label_values(&[&event.kind]).inc();
        }
        match event.kind.as_str() {
            "engine.escalation" => {
                if let Some(c) = &self.escalations {
                    c.inc();
                }
            }
            "engine.release" => {
                if let Some(c) = &self.releases {
                    c.inc();
                }
            }
            "engine.step" => {
                if let Some(g) = &self.pressure {
                    if let Some(p) = event.data.get("pressure").and_then(|v| v.as_f64()) {
                        g.with_label_values(&[&event.execution_id]).set(p);
                    }
                }
                if let Some(h) = &self.step_delta {
                    if let Some(d) = event.data.get("delta").and_then(|v| v.as_f64()) {
                        h.observe(d);
                    }
                }
            }
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::collections::BTreeMap;

    struct CountingCounter {
        counter: Arc<AtomicUsize>,
    }
    impl Counter for CountingCounter {
        fn inc(&self) {
            self.counter.fetch_add(1, Ordering::SeqCst);
        }
    }

    struct CountingCounterVec {
        counter: Arc<AtomicUsize>,
    }
    impl CounterVec for CountingCounterVec {
        fn with_label_values(&self, _: &[&str]) -> Box<dyn Counter> {
            Box::new(CountingCounter {
                counter: self.counter.clone(),
            })
        }
    }

    #[test]
    fn sink_increments_counter_per_event() {
        let counter = Arc::new(AtomicUsize::new(0));
        let sink = PrometheusSink {
            events: Some(Arc::new(CountingCounterVec {
                counter: counter.clone(),
            })),
            escalations: None,
            releases: None,
            pressure: None,
            step_delta: None,
        };
        for _ in 0..5 {
            sink.emit(&Event::new("e", "engine.step", 0.0, BTreeMap::new()));
        }
        assert_eq!(counter.load(Ordering::SeqCst), 5);
    }
}

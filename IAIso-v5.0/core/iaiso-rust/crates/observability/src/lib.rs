//! IAIso OpenTelemetry tracing sink.
//!
//! Structurally typed against the OTel trace API. The official
//! `opentelemetry` crate's `Tracer` and `Span` satisfy these traits
//! with thin adapters.

use iaiso_audit::{Event, Sink};
use parking_lot::Mutex;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;

/// A span attribute. Mirrors the JSON shapes typically emitted.
pub type AttrMap = HashMap<String, Value>;

/// A trait representing an OTel span.
pub trait Span: Send + Sync {
    fn add_event(&self, name: &str, attrs: &AttrMap);
    fn set_attribute(&self, key: &str, value: &Value);
    fn end(&self);
}

/// A trait representing an OTel tracer.
pub trait Tracer: Send + Sync {
    fn start_span(&self, name: &str, attrs: &AttrMap) -> Arc<dyn Span>;
}

/// An audit sink that opens one OTel span per execution and attaches
/// every event as a span event.
pub struct OtelSpanSink {
    tracer: Arc<dyn Tracer>,
    span_name: String,
    spans: Mutex<HashMap<String, Arc<dyn Span>>>,
}

impl OtelSpanSink {
    pub fn new(tracer: Arc<dyn Tracer>, span_name: impl Into<String>) -> Self {
        let mut name = span_name.into();
        if name.is_empty() {
            name = "iaiso.execution".to_string();
        }
        Self {
            tracer,
            span_name: name,
            spans: Mutex::new(HashMap::new()),
        }
    }

    /// End any open spans. Useful at shutdown.
    pub fn close_all(&self) {
        let mut map = self.spans.lock();
        for (_, span) in map.drain() {
            span.end();
        }
    }
}

impl Sink for OtelSpanSink {
    fn emit(&self, event: &Event) {
        let span = {
            let mut map = self.spans.lock();
            if event.kind == "engine.init" {
                let mut attrs = AttrMap::new();
                attrs.insert(
                    "iaiso.execution_id".to_string(),
                    Value::String(event.execution_id.clone()),
                );
                let span = self.tracer.start_span(
                    &format!("{}:{}", self.span_name, event.execution_id),
                    &attrs,
                );
                map.insert(event.execution_id.clone(), span.clone());
                Some(span)
            } else {
                map.get(&event.execution_id).cloned()
            }
        };
        if let Some(span) = span {
            let mut attrs = AttrMap::new();
            attrs.insert(
                "iaiso.schema_version".to_string(),
                Value::String(event.schema_version.clone()),
            );
            for (k, v) in &event.data {
                attrs.insert(k.clone(), v.clone());
            }
            span.add_event(&event.kind, &attrs);

            match event.kind.as_str() {
                "engine.step" => {
                    if let Some(p) = event.data.get("pressure") {
                        span.set_attribute("iaiso.pressure", p);
                    }
                }
                "engine.escalation" => {
                    span.set_attribute("iaiso.escalated", &Value::Bool(true));
                }
                "engine.release" => {
                    span.set_attribute("iaiso.released", &Value::Bool(true));
                }
                "execution.closed" => {
                    span.end();
                    self.spans.lock().remove(&event.execution_id);
                }
                _ => {}
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;
    use std::sync::atomic::{AtomicUsize, Ordering};

    struct CountingSpan {
        events: Arc<AtomicUsize>,
        ended: Arc<AtomicUsize>,
    }
    impl Span for CountingSpan {
        fn add_event(&self, _: &str, _: &AttrMap) {
            self.events.fetch_add(1, Ordering::SeqCst);
        }
        fn set_attribute(&self, _: &str, _: &Value) {}
        fn end(&self) {
            self.ended.fetch_add(1, Ordering::SeqCst);
        }
    }

    struct CountingTracer {
        events: Arc<AtomicUsize>,
        ended: Arc<AtomicUsize>,
    }
    impl Tracer for CountingTracer {
        fn start_span(&self, _: &str, _: &AttrMap) -> Arc<dyn Span> {
            Arc::new(CountingSpan {
                events: self.events.clone(),
                ended: self.ended.clone(),
            })
        }
    }

    #[test]
    fn opens_span_on_init_and_attaches_events() {
        let events = Arc::new(AtomicUsize::new(0));
        let ended = Arc::new(AtomicUsize::new(0));
        let tracer = Arc::new(CountingTracer {
            events: events.clone(),
            ended: ended.clone(),
        });
        let sink = OtelSpanSink::new(tracer, "iaiso.execution");

        sink.emit(&Event::new("exec-1", "engine.init", 0.0, BTreeMap::new()));
        sink.emit(&Event::new("exec-1", "engine.step", 0.1, BTreeMap::new()));
        sink.emit(&Event::new("exec-1", "execution.closed", 0.2, BTreeMap::new()));
        // 3 events attached to the span; ended once on close.
        assert_eq!(events.load(Ordering::SeqCst), 3);
        assert_eq!(ended.load(Ordering::SeqCst), 1);
    }
}

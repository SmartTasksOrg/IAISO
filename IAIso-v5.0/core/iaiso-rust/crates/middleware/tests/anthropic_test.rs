use iaiso_audit::MemorySink;
use iaiso_core::{BoundedExecution, BoundedExecutionOptions, PressureConfig};
use iaiso_middleware::{
    anthropic::{BoundedClient, Client, ContentBlock, Options, Response, Usage},
    MiddlewareError,
};
use serde_json::{json, Value};
use std::sync::Arc;

struct StubClient {
    resp: Response,
}

impl Client for StubClient {
    fn messages_create(&self, _params: &Value) -> Result<Response, String> {
        Ok(self.resp.clone())
    }
}

#[test]
fn accounts_tokens_and_tool_calls() {
    let sink = Arc::new(MemorySink::new());
    let exec = BoundedExecution::start(BoundedExecutionOptions {
        audit_sink: sink.clone(),
        ..Default::default()
    })
    .unwrap();
    let raw = StubClient {
        resp: Response {
            model: "claude-opus-4-7".to_string(),
            usage: Usage { input_tokens: 100, output_tokens: 250 },
            content: vec![
                ContentBlock { kind: "text".to_string() },
                ContentBlock { kind: "tool_use".to_string() },
                ContentBlock { kind: "tool_use".to_string() },
            ],
        },
    };
    let client = BoundedClient::new(raw, &exec, Options::default());
    client.messages_create(&json!({})).unwrap();

    let step_event = sink
        .events()
        .iter()
        .find(|e| e.kind == "engine.step")
        .cloned()
        .expect("missing engine.step");
    assert_eq!(step_event.data["tokens"].as_u64().unwrap(), 350);
    assert_eq!(step_event.data["tool_calls"].as_u64().unwrap(), 2);
}

#[test]
fn raises_on_escalation_when_opted_in() {
    let cfg = PressureConfig {
        escalation_threshold: 0.4,
        release_threshold: 0.95,
        depth_coefficient: 0.5,
        dissipation_per_step: 0.0,
        ..PressureConfig::default()
    };
    let exec = BoundedExecution::start(BoundedExecutionOptions {
        config: cfg,
        ..Default::default()
    })
    .unwrap();
    exec.record_step(iaiso_core::StepInput {
        depth: 1,
        ..Default::default()
    })
    .unwrap();
    // Now escalated. Calling should raise.
    let raw = StubClient {
        resp: Response::default(),
    };
    let client = BoundedClient::new(
        raw,
        &exec,
        Options { raise_on_escalation: true },
    );
    let r = client.messages_create(&json!({}));
    assert!(matches!(r, Err(MiddlewareError::EscalationRaised)));
}

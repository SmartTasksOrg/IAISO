//! Anthropic Messages API wrapper.

use crate::MiddlewareError;
use iaiso_core::{BoundedExecution, StepInput, StepOutcome};
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Usage {
    #[serde(default)]
    pub input_tokens: u64,
    #[serde(default)]
    pub output_tokens: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ContentBlock {
    #[serde(rename = "type")]
    pub kind: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Response {
    #[serde(default)]
    pub model: String,
    #[serde(default)]
    pub usage: Usage,
    #[serde(default)]
    pub content: Vec<ContentBlock>,
}

/// Structural interface a wrapped Anthropic client must satisfy.
pub trait Client: Send + Sync {
    fn messages_create(&self, params: &Value) -> Result<Response, String>;
}

#[derive(Debug, Clone, Copy, Default)]
pub struct Options {
    pub raise_on_escalation: bool,
}

pub struct BoundedClient<'a, C: Client> {
    raw: C,
    execution: &'a BoundedExecution,
    opts: Options,
}

impl<'a, C: Client> BoundedClient<'a, C> {
    pub fn new(raw: C, execution: &'a BoundedExecution, opts: Options) -> Self {
        Self { raw, execution, opts }
    }

    pub fn messages_create(&self, params: &Value) -> Result<Response, MiddlewareError> {
        match self.execution.check() {
            StepOutcome::Locked => return Err(MiddlewareError::Locked),
            StepOutcome::Escalated if self.opts.raise_on_escalation => {
                return Err(MiddlewareError::EscalationRaised)
            }
            _ => {}
        }
        let resp = self
            .raw
            .messages_create(params)
            .map_err(MiddlewareError::Provider)?;
        let tokens = resp.usage.input_tokens + resp.usage.output_tokens;
        let tool_calls = resp
            .content
            .iter()
            .filter(|b| b.kind == "tool_use")
            .count() as u64;
        let model = if resp.model.is_empty() {
            "unknown".to_string()
        } else {
            resp.model.clone()
        };
        let _ = self.execution.record_step(StepInput {
            tokens,
            tool_calls,
            tag: Some(format!("anthropic.messages.create:{}", model)),
            ..Default::default()
        });
        Ok(resp)
    }
}

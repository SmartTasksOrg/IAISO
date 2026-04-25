//! Cohere API wrapper.

use crate::MiddlewareError;
use iaiso_core::{BoundedExecution, StepInput, StepOutcome};
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct BilledUnits {
    #[serde(default)]
    pub input_tokens: u64,
    #[serde(default)]
    pub output_tokens: u64,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Meta {
    #[serde(default)]
    pub tokens: Option<BilledUnits>,
    #[serde(default, rename = "billedUnits")]
    pub billed_units: Option<BilledUnits>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ToolCall {
    pub name: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Response {
    #[serde(default)]
    pub model: String,
    #[serde(default)]
    pub meta: Meta,
    #[serde(default, rename = "toolCalls")]
    pub tool_calls: Vec<ToolCall>,
}

pub trait Client: Send + Sync {
    fn chat(&self, params: &Value) -> Result<Response, String>;
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

    pub fn chat(&self, params: &Value) -> Result<Response, MiddlewareError> {
        match self.execution.check() {
            StepOutcome::Locked => return Err(MiddlewareError::Locked),
            StepOutcome::Escalated if self.opts.raise_on_escalation => {
                return Err(MiddlewareError::EscalationRaised)
            }
            _ => {}
        }
        let resp = self.raw.chat(params).map_err(MiddlewareError::Provider)?;
        let bucket = resp
            .meta
            .tokens
            .as_ref()
            .or(resp.meta.billed_units.as_ref());
        let tokens = bucket
            .map(|b| b.input_tokens + b.output_tokens)
            .unwrap_or(0);
        let tool_calls = resp.tool_calls.len() as u64;
        let model = if resp.model.is_empty() {
            "unknown".to_string()
        } else {
            resp.model.clone()
        };
        let _ = self.execution.record_step(StepInput {
            tokens,
            tool_calls,
            tag: Some(format!("cohere.chat:{}", model)),
            ..Default::default()
        });
        Ok(resp)
    }
}

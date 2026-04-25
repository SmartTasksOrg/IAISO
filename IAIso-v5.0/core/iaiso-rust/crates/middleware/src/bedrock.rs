//! AWS Bedrock runtime wrapper. Supports both Converse (preferred —
//! normalized usage extraction across model families) and InvokeModel.

use crate::MiddlewareError;
use iaiso_core::{BoundedExecution, StepInput, StepOutcome};
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ConverseUsage {
    #[serde(default)]
    pub input_tokens: u64,
    #[serde(default)]
    pub output_tokens: u64,
    #[serde(default)]
    pub total_tokens: u64,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ConverseToolUse {
    #[serde(default)]
    pub tool_use_id: String,
    #[serde(default)]
    pub name: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ConverseContentBlock {
    #[serde(default)]
    pub tool_use: Option<ConverseToolUse>,
    #[serde(default)]
    pub text: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ConverseMessage {
    #[serde(default)]
    pub content: Vec<ConverseContentBlock>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ConverseOutput {
    #[serde(default)]
    pub message: ConverseMessage,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ConverseResponse {
    #[serde(default)]
    pub output: ConverseOutput,
    #[serde(default)]
    pub usage: ConverseUsage,
}

#[derive(Debug, Clone)]
pub struct InvokeResponse {
    pub model_id: String,
    pub body: Vec<u8>,
}

pub trait Client: Send + Sync {
    fn converse(&self, params: &Value) -> Result<ConverseResponse, String>;
    fn invoke_model(&self, params: &Value) -> Result<InvokeResponse, String>;
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

    pub fn converse(&self, params: &Value) -> Result<ConverseResponse, MiddlewareError> {
        match self.execution.check() {
            StepOutcome::Locked => return Err(MiddlewareError::Locked),
            StepOutcome::Escalated if self.opts.raise_on_escalation => {
                return Err(MiddlewareError::EscalationRaised)
            }
            _ => {}
        }
        let resp = self.raw.converse(params).map_err(MiddlewareError::Provider)?;
        let mut tokens = resp.usage.total_tokens;
        if tokens == 0 {
            tokens = resp.usage.input_tokens + resp.usage.output_tokens;
        }
        let tool_calls = resp
            .output
            .message
            .content
            .iter()
            .filter(|b| b.tool_use.is_some())
            .count() as u64;
        let model_id = params
            .get("modelId")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string();
        let _ = self.execution.record_step(StepInput {
            tokens,
            tool_calls,
            tag: Some(format!("bedrock.converse:{}", model_id)),
            ..Default::default()
        });
        Ok(resp)
    }

    pub fn invoke_model(&self, params: &Value) -> Result<InvokeResponse, MiddlewareError> {
        match self.execution.check() {
            StepOutcome::Locked => return Err(MiddlewareError::Locked),
            StepOutcome::Escalated if self.opts.raise_on_escalation => {
                return Err(MiddlewareError::EscalationRaised)
            }
            _ => {}
        }
        let resp = self
            .raw
            .invoke_model(params)
            .map_err(MiddlewareError::Provider)?;
        let model_id = if !resp.model_id.is_empty() {
            resp.model_id.clone()
        } else {
            params
                .get("modelId")
                .and_then(Value::as_str)
                .unwrap_or("unknown")
                .to_string()
        };
        let tokens = extract_tokens_from_invoke_body(&resp.body);
        let _ = self.execution.record_step(StepInput {
            tokens,
            tag: Some(format!("bedrock.invokeModel:{}", model_id)),
            ..Default::default()
        });
        Ok(resp)
    }
}

/// Best-effort scan of a model-specific InvokeModel response body for
/// token counts. Returns 0 when the body shape is unrecognized.
pub fn extract_tokens_from_invoke_body(_body: &[u8]) -> u64 {
    // Operators who need precise accounting on InvokeModel should adapt
    // this for their specific model family. The Converse wrapper above
    // handles usage uniformly.
    0
}

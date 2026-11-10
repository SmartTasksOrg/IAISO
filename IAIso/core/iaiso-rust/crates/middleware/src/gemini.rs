//! Google Gemini / Vertex AI wrapper.

use crate::MiddlewareError;
use iaiso_core::{BoundedExecution, StepInput, StepOutcome};
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct UsageMetadata {
    #[serde(default)]
    pub prompt_token_count: u64,
    #[serde(default)]
    pub candidates_token_count: u64,
    #[serde(default)]
    pub total_token_count: u64,
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ContentPart {
    #[serde(default)]
    pub function_call: Option<Value>,
    #[serde(default)]
    pub text: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Content {
    #[serde(default)]
    pub parts: Vec<ContentPart>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Candidate {
    #[serde(default)]
    pub content: Content,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Response {
    #[serde(default)]
    pub usage_metadata: UsageMetadata,
    #[serde(default)]
    pub candidates: Vec<Candidate>,
}

pub trait Model: Send + Sync {
    fn generate_content(&self, request: &Value) -> Result<Response, String>;
    fn model_name(&self) -> &str;
}

#[derive(Debug, Clone, Copy, Default)]
pub struct Options {
    pub raise_on_escalation: bool,
}

pub struct BoundedModel<'a, M: Model> {
    raw: M,
    execution: &'a BoundedExecution,
    opts: Options,
}

impl<'a, M: Model> BoundedModel<'a, M> {
    pub fn new(raw: M, execution: &'a BoundedExecution, opts: Options) -> Self {
        Self { raw, execution, opts }
    }

    pub fn generate_content(&self, request: &Value) -> Result<Response, MiddlewareError> {
        match self.execution.check() {
            StepOutcome::Locked => return Err(MiddlewareError::Locked),
            StepOutcome::Escalated if self.opts.raise_on_escalation => {
                return Err(MiddlewareError::EscalationRaised)
            }
            _ => {}
        }
        let resp = self
            .raw
            .generate_content(request)
            .map_err(MiddlewareError::Provider)?;
        let mut tokens = resp.usage_metadata.total_token_count;
        if tokens == 0 {
            tokens = resp.usage_metadata.prompt_token_count
                + resp.usage_metadata.candidates_token_count;
        }
        let tool_calls: u64 = resp
            .candidates
            .iter()
            .map(|c| {
                c.content
                    .parts
                    .iter()
                    .filter(|p| p.function_call.is_some())
                    .count() as u64
            })
            .sum();
        let model = self.raw.model_name().to_string();
        let _ = self.execution.record_step(StepInput {
            tokens,
            tool_calls,
            tag: Some(format!(
                "gemini.generateContent:{}",
                if model.is_empty() { "unknown" } else { &model }
            )),
            ..Default::default()
        });
        Ok(resp)
    }
}

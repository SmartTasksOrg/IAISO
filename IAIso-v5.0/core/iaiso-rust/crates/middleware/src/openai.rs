//! OpenAI / OpenAI-compatible chat-completions wrapper. Satisfies
//! Azure OpenAI, vLLM, TGI, LiteLLM proxy, Together, Groq, etc.

use crate::MiddlewareError;
use iaiso_core::{BoundedExecution, StepInput, StepOutcome};
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Usage {
    #[serde(default)]
    pub prompt_tokens: u64,
    #[serde(default)]
    pub completion_tokens: u64,
    #[serde(default)]
    pub total_tokens: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ToolCall {
    pub id: String,
    #[serde(default)]
    pub r#type: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Message {
    #[serde(default)]
    pub tool_calls: Vec<ToolCall>,
    #[serde(default)]
    pub function_call: Option<Value>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Choice {
    #[serde(default)]
    pub message: Message,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Response {
    #[serde(default)]
    pub model: String,
    #[serde(default)]
    pub usage: Usage,
    #[serde(default)]
    pub choices: Vec<Choice>,
}

pub trait Client: Send + Sync {
    fn chat_completions_create(&self, params: &Value) -> Result<Response, String>;
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

    pub fn chat_completions_create(&self, params: &Value) -> Result<Response, MiddlewareError> {
        match self.execution.check() {
            StepOutcome::Locked => return Err(MiddlewareError::Locked),
            StepOutcome::Escalated if self.opts.raise_on_escalation => {
                return Err(MiddlewareError::EscalationRaised)
            }
            _ => {}
        }
        let resp = self
            .raw
            .chat_completions_create(params)
            .map_err(MiddlewareError::Provider)?;
        let mut tokens = resp.usage.total_tokens;
        if tokens == 0 {
            tokens = resp.usage.prompt_tokens + resp.usage.completion_tokens;
        }
        let tool_calls = resp
            .choices
            .iter()
            .map(|c| c.message.tool_calls.len() as u64 + c.message.function_call.is_some() as u64)
            .sum();
        let model = if resp.model.is_empty() {
            "unknown".to_string()
        } else {
            resp.model.clone()
        };
        let _ = self.execution.record_step(StepInput {
            tokens,
            tool_calls,
            tag: Some(format!("openai.chat.completions.create:{}", model)),
            ..Default::default()
        });
        Ok(resp)
    }
}

//! IAIso LLM provider middleware.
//!
//! Each module wraps an upstream LLM client so every call is accounted
//! against a [`BoundedExecution`]. The wrapper is structurally typed —
//! you supply a thin adapter satisfying the provider-specific `Client`
//! trait (e.g. wrapping the official Anthropic Rust SDK, the
//! `async-openai` crate, `aws-sdk-bedrockruntime`, etc).
//!
//! Token counts come from the response's usage field; tool calls are
//! counted from response content blocks. If the execution is locked or
//! escalated (with raise-on-escalation enabled), calls fail fast
//! BEFORE reaching the provider.

use thiserror::Error;

/// Returned by middleware when raise-on-escalation is enabled and the
/// engine has already escalated.
#[derive(Debug, Error)]
pub enum MiddlewareError {
    #[error("execution escalated; raise-on-escalation enabled")]
    EscalationRaised,
    #[error("execution locked")]
    Locked,
    #[error("provider error: {0}")]
    Provider(String),
}

pub mod anthropic;
pub mod bedrock;
pub mod cohere;
pub mod gemini;
pub mod litellm;
pub mod mistral;
pub mod openai;

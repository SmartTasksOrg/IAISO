//! LiteLLM proxy-pattern helper.
//!
//! LiteLLM's primary integration on the server side is its proxy
//! server, which exposes an OpenAI-compatible HTTP endpoint that
//! routes to any of 100+ underlying providers. On the client side,
//! point an OpenAI-compatible client at the proxy URL and account for
//! the call via the [`crate::openai`] middleware — token accounting
//! works identically to vanilla OpenAI.
//!
//! This module exists primarily to make the integration discoverable
//! alongside the other LLM middleware. It exports a tiny [`ProxyConfig`]
//! struct that documents the typical fields you'd configure on your
//! underlying client.

use std::collections::HashMap;

#[derive(Debug, Clone, Default)]
pub struct ProxyConfig {
    /// Base URL, e.g. `https://litellm.example.com/v1`.
    pub base_url: String,
    /// Master key or virtual key.
    pub api_key: String,
    /// Optional default headers, e.g. `X-Tenant` for multi-tenant.
    pub default_headers: HashMap<String, String>,
}

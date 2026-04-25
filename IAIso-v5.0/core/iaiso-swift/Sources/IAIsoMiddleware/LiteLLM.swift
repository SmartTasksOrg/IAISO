import Foundation

/// LiteLLM proxy-pattern helper.
///
/// LiteLLM's primary integration is its proxy server, which exposes an
/// OpenAI-compatible HTTP endpoint that routes to any of 100+ underlying
/// providers. On the client side, point an OpenAI-compatible client at
/// the proxy URL and account for the call via
/// `IAIsoMiddleware.OpenAI.BoundedClient` — token accounting works
/// identically to vanilla OpenAI.
///
/// This module exists primarily to make the integration discoverable
/// alongside the other LLM middleware. `ProxyConfig` documents the
/// typical fields you would configure on your underlying client.
public enum LiteLLM {
    public struct ProxyConfig: Sendable, Equatable {
        public let baseURL: String
        public let apiKey: String
        public let defaultHeaders: [String: String]

        public init(
            baseURL: String,
            apiKey: String = "",
            defaultHeaders: [String: String] = [:]
        ) {
            self.baseURL = baseURL
            self.apiKey = apiKey
            self.defaultHeaders = defaultHeaders
        }
    }
}

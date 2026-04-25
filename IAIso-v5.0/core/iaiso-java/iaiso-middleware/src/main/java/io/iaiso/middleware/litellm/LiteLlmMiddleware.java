package io.iaiso.middleware.litellm;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * LiteLLM proxy-pattern helper.
 *
 * <p>LiteLLM's primary integration is its proxy server, which exposes
 * an OpenAI-compatible HTTP endpoint that routes to any of 100+
 * underlying providers. On the client side, point an OpenAI-compatible
 * client at the proxy URL and account for the call via
 * {@link io.iaiso.middleware.openai.OpenAiMiddleware} — token
 * accounting works identically to vanilla OpenAI.
 *
 * <p>This module exists primarily to make the integration discoverable
 * alongside the other LLM middleware. {@link ProxyConfig} documents the
 * typical fields you'd configure on your underlying client.
 */
public final class LiteLlmMiddleware {
    private LiteLlmMiddleware() {}

    public static final class ProxyConfig {
        public final String baseUrl;
        public final String apiKey;
        public final Map<String, String> defaultHeaders;

        public ProxyConfig(String baseUrl, String apiKey, Map<String, String> defaultHeaders) {
            this.baseUrl = baseUrl;
            this.apiKey = apiKey;
            this.defaultHeaders = Collections.unmodifiableMap(
                defaultHeaders != null ? new HashMap<>(defaultHeaders) : new HashMap<>());
        }
    }
}

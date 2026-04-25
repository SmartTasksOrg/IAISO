<?php

declare(strict_types=1);

namespace IAIso\Middleware\LiteLlm;

/**
 * LiteLLM proxy-pattern helper.
 *
 * <p>LiteLLM's primary integration is its proxy server, which exposes
 * an OpenAI-compatible HTTP endpoint that routes to any of 100+
 * underlying providers. On the client side, point an OpenAI-compatible
 * client at the proxy URL and account for the call via
 * {@see \IAIso\Middleware\OpenAi\BoundedClient} — token accounting
 * works identically to vanilla OpenAI.
 *
 * <p>This module exists primarily to make the integration discoverable
 * alongside the other LLM middleware. {@see ProxyConfig} documents the
 * typical fields you would configure on your underlying client.
 */
final class ProxyConfig
{
    /** @param array<string,string> $defaultHeaders */
    public function __construct(
        public readonly string $baseUrl,
        public readonly string $apiKey = '',
        public readonly array $defaultHeaders = [],
    ) {}
}

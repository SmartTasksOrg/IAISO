using System.Collections.Generic;

namespace Iaiso.Middleware.LiteLlm;

/// <summary>
/// LiteLLM proxy-pattern helper.
///
/// LiteLLM's primary integration is its proxy server, which exposes
/// an OpenAI-compatible HTTP endpoint that routes to any of 100+
/// underlying providers. On the client side, point an OpenAI-compatible
/// client at the proxy URL and account for the call via
/// <see cref="OpenAi.BoundedOpenAiClient"/> — token accounting works
/// identically to vanilla OpenAI.
///
/// This namespace exists primarily to make the integration discoverable
/// alongside the other LLM middleware. <see cref="ProxyConfig"/>
/// documents the typical fields you'd configure on your underlying
/// client.
/// </summary>
public sealed class ProxyConfig
{
    public string BaseUrl { get; }
    public string? ApiKey { get; }
    public IReadOnlyDictionary<string, string> DefaultHeaders { get; }

    public ProxyConfig(string baseUrl, string? apiKey, IReadOnlyDictionary<string, string>? defaultHeaders)
    {
        BaseUrl = baseUrl;
        ApiKey = apiKey;
        DefaultHeaders = defaultHeaders is null
            ? new Dictionary<string, string>()
            : new Dictionary<string, string>(defaultHeaders);
    }
}

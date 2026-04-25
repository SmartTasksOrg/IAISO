using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Core;

namespace Iaiso.Middleware.Anthropic;

/// <summary>Structural client interface — one method per Anthropic operation.</summary>
public interface IAnthropicClient
{
    AnthropicResponse MessagesCreate(JsonObject @params);
}

/// <summary>Anthropic response — minimal subset of fields we need.</summary>
public sealed class AnthropicResponse
{
    public string Model { get; }
    public long InputTokens { get; }
    public long OutputTokens { get; }
    public IReadOnlyList<ContentBlock> Content { get; }

    public AnthropicResponse(string model, long inputTokens, long outputTokens,
                             IReadOnlyList<ContentBlock>? content)
    {
        Model = model;
        InputTokens = inputTokens;
        OutputTokens = outputTokens;
        Content = content ?? new List<ContentBlock>();
    }
}

/// <summary>A content block in a response.</summary>
public sealed class ContentBlock
{
    public string Type { get; }
    public ContentBlock(string type) { Type = type; }
}

/// <summary>Options for <see cref="BoundedAnthropicClient"/>.</summary>
public sealed class AnthropicOptions
{
    public bool RaiseOnEscalation { get; set; }
    public static AnthropicOptions Defaults() => new();
}

/// <summary>
/// Wraps an <see cref="IAnthropicClient"/> so every call is accounted
/// against a <see cref="BoundedExecution"/>.
/// </summary>
public sealed class BoundedAnthropicClient
{
    private readonly IAnthropicClient _raw;
    private readonly BoundedExecution _execution;
    private readonly AnthropicOptions _opts;

    public BoundedAnthropicClient(IAnthropicClient raw, BoundedExecution execution, AnthropicOptions? opts = null)
    {
        _raw = raw;
        _execution = execution;
        _opts = opts ?? AnthropicOptions.Defaults();
    }

    public AnthropicResponse MessagesCreate(JsonObject @params)
    {
        var pre = _execution.Check();
        if (pre == StepOutcome.Locked) throw new MiddlewareException.Locked();
        if (pre == StepOutcome.Escalated && _opts.RaiseOnEscalation)
            throw new MiddlewareException.EscalationRaised();

        AnthropicResponse resp;
        try { resp = _raw.MessagesCreate(@params); }
        catch (System.Exception e) { throw new MiddlewareException.Provider(e.Message, e); }

        long tokens = resp.InputTokens + resp.OutputTokens;
        long toolCalls = 0;
        foreach (var b in resp.Content) if (b.Type == "tool_use") toolCalls++;
        string model = string.IsNullOrEmpty(resp.Model) ? "unknown" : resp.Model;
        _execution.RecordStep(new StepInput
        {
            Tokens = tokens,
            ToolCalls = toolCalls,
            Tag = $"anthropic.messages.create:{model}",
        });
        return resp;
    }
}

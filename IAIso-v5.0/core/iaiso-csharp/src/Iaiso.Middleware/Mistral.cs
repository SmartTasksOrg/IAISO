using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Core;

namespace Iaiso.Middleware.Mistral;

/// <summary>IAIso wrapper for Mistral chat.</summary>
public interface IMistralClient
{
    MistralResponse ChatComplete(JsonObject @params);
}

public sealed class MistralUsage
{
    public long PromptTokens { get; set; }
    public long CompletionTokens { get; set; }
    public long TotalTokens { get; set; }
}

public sealed class MistralChoice
{
    public IReadOnlyList<string> ToolCalls { get; }
    public MistralChoice(IReadOnlyList<string>? toolCalls)
    {
        ToolCalls = toolCalls ?? new List<string>();
    }
}

public sealed class MistralResponse
{
    public string Model { get; }
    public MistralUsage Usage { get; }
    public IReadOnlyList<MistralChoice> Choices { get; }
    public MistralResponse(string model, MistralUsage? usage, IReadOnlyList<MistralChoice>? choices)
    {
        Model = model;
        Usage = usage ?? new MistralUsage();
        Choices = choices ?? new List<MistralChoice>();
    }
}

public sealed class MistralOptions
{
    public bool RaiseOnEscalation { get; set; }
    public static MistralOptions Defaults() => new();
}

public sealed class BoundedMistralClient
{
    private readonly IMistralClient _raw;
    private readonly BoundedExecution _execution;
    private readonly MistralOptions _opts;

    public BoundedMistralClient(IMistralClient raw, BoundedExecution execution, MistralOptions? opts = null)
    {
        _raw = raw;
        _execution = execution;
        _opts = opts ?? MistralOptions.Defaults();
    }

    public MistralResponse ChatComplete(JsonObject @params)
    {
        var pre = _execution.Check();
        if (pre == StepOutcome.Locked) throw new MiddlewareException.Locked();
        if (pre == StepOutcome.Escalated && _opts.RaiseOnEscalation)
            throw new MiddlewareException.EscalationRaised();

        MistralResponse resp;
        try { resp = _raw.ChatComplete(@params); }
        catch (System.Exception e) { throw new MiddlewareException.Provider(e.Message, e); }

        long tokens = resp.Usage.TotalTokens;
        if (tokens == 0) tokens = resp.Usage.PromptTokens + resp.Usage.CompletionTokens;
        long toolCalls = 0;
        foreach (var c in resp.Choices) toolCalls += c.ToolCalls.Count;
        string model = string.IsNullOrEmpty(resp.Model) ? "unknown" : resp.Model;
        _execution.RecordStep(new StepInput
        {
            Tokens = tokens,
            ToolCalls = toolCalls,
            Tag = $"mistral.chat.complete:{model}",
        });
        return resp;
    }
}

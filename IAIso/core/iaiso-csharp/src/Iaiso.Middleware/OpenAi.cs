using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Core;

namespace Iaiso.Middleware.OpenAi;

/// <summary>
/// Structural client interface for OpenAI and OpenAI-compatible APIs
/// (Azure OpenAI, vLLM, TGI, LiteLLM proxy, Together, Groq, etc.).
/// </summary>
public interface IOpenAiClient
{
    OpenAiResponse ChatCompletionsCreate(JsonObject @params);
}

public sealed class Usage
{
    public long PromptTokens { get; set; }
    public long CompletionTokens { get; set; }
    public long TotalTokens { get; set; }
}

public sealed class ToolCall
{
    public string Id { get; }
    public ToolCall(string id) { Id = id; }
}

public sealed class Choice
{
    public IReadOnlyList<ToolCall> ToolCalls { get; }
    public bool HasFunctionCall { get; }
    public Choice(IReadOnlyList<ToolCall>? toolCalls, bool hasFunctionCall)
    {
        ToolCalls = toolCalls ?? new List<ToolCall>();
        HasFunctionCall = hasFunctionCall;
    }
}

public sealed class OpenAiResponse
{
    public string Model { get; }
    public Usage Usage { get; }
    public IReadOnlyList<Choice> Choices { get; }
    public OpenAiResponse(string model, Usage? usage, IReadOnlyList<Choice>? choices)
    {
        Model = model;
        Usage = usage ?? new Usage();
        Choices = choices ?? new List<Choice>();
    }
}

public sealed class OpenAiOptions
{
    public bool RaiseOnEscalation { get; set; }
    public static OpenAiOptions Defaults() => new();
}

public sealed class BoundedOpenAiClient
{
    private readonly IOpenAiClient _raw;
    private readonly BoundedExecution _execution;
    private readonly OpenAiOptions _opts;

    public BoundedOpenAiClient(IOpenAiClient raw, BoundedExecution execution, OpenAiOptions? opts = null)
    {
        _raw = raw;
        _execution = execution;
        _opts = opts ?? OpenAiOptions.Defaults();
    }

    public OpenAiResponse ChatCompletionsCreate(JsonObject @params)
    {
        var pre = _execution.Check();
        if (pre == StepOutcome.Locked) throw new MiddlewareException.Locked();
        if (pre == StepOutcome.Escalated && _opts.RaiseOnEscalation)
            throw new MiddlewareException.EscalationRaised();

        OpenAiResponse resp;
        try { resp = _raw.ChatCompletionsCreate(@params); }
        catch (System.Exception e) { throw new MiddlewareException.Provider(e.Message, e); }

        long tokens = resp.Usage.TotalTokens;
        if (tokens == 0) tokens = resp.Usage.PromptTokens + resp.Usage.CompletionTokens;
        long toolCalls = 0;
        foreach (var c in resp.Choices)
        {
            toolCalls += c.ToolCalls.Count;
            if (c.HasFunctionCall) toolCalls++;
        }
        string model = string.IsNullOrEmpty(resp.Model) ? "unknown" : resp.Model;
        _execution.RecordStep(new StepInput
        {
            Tokens = tokens,
            ToolCalls = toolCalls,
            Tag = $"openai.chat.completions.create:{model}",
        });
        return resp;
    }
}

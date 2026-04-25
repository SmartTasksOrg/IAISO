using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Core;

namespace Iaiso.Middleware.Bedrock;

/// <summary>
/// IAIso wrapper for AWS Bedrock runtime. Supports both Converse API
/// (preferred — normalized usage extraction) and the lower-level
/// InvokeModel API.
/// </summary>
public interface IBedrockClient
{
    ConverseResponse Converse(JsonObject @params);
    InvokeResponse InvokeModel(JsonObject @params);
}

public sealed class ConverseUsage
{
    public long InputTokens { get; set; }
    public long OutputTokens { get; set; }
    public long TotalTokens { get; set; }
}

public sealed class ConverseContentBlock
{
    public bool HasToolUse { get; }
    public ConverseContentBlock(bool hasToolUse) { HasToolUse = hasToolUse; }
}

public sealed class ConverseResponse
{
    public ConverseUsage Usage { get; }
    public IReadOnlyList<ConverseContentBlock> Content { get; }
    public ConverseResponse(ConverseUsage? usage, IReadOnlyList<ConverseContentBlock>? content)
    {
        Usage = usage ?? new ConverseUsage();
        Content = content ?? new List<ConverseContentBlock>();
    }
}

public sealed class InvokeResponse
{
    public string ModelId { get; }
    public byte[] Body { get; }
    public InvokeResponse(string modelId, byte[]? body)
    {
        ModelId = modelId;
        Body = body ?? System.Array.Empty<byte>();
    }
}

public sealed class BedrockOptions
{
    public bool RaiseOnEscalation { get; set; }
    public static BedrockOptions Defaults() => new();
}

public sealed class BoundedBedrockClient
{
    private readonly IBedrockClient _raw;
    private readonly BoundedExecution _execution;
    private readonly BedrockOptions _opts;

    public BoundedBedrockClient(IBedrockClient raw, BoundedExecution execution, BedrockOptions? opts = null)
    {
        _raw = raw;
        _execution = execution;
        _opts = opts ?? BedrockOptions.Defaults();
    }

    public ConverseResponse Converse(JsonObject @params)
    {
        CheckState();
        ConverseResponse resp;
        try { resp = _raw.Converse(@params); }
        catch (System.Exception e) { throw new MiddlewareException.Provider(e.Message, e); }

        long tokens = resp.Usage.TotalTokens;
        if (tokens == 0) tokens = resp.Usage.InputTokens + resp.Usage.OutputTokens;
        long toolCalls = 0;
        foreach (var b in resp.Content) if (b.HasToolUse) toolCalls++;
        string modelId = @params["modelId"]?.GetValue<string>() ?? "unknown";
        _execution.RecordStep(new StepInput
        {
            Tokens = tokens,
            ToolCalls = toolCalls,
            Tag = $"bedrock.converse:{modelId}",
        });
        return resp;
    }

    public InvokeResponse InvokeModel(JsonObject @params)
    {
        CheckState();
        InvokeResponse resp;
        try { resp = _raw.InvokeModel(@params); }
        catch (System.Exception e) { throw new MiddlewareException.Provider(e.Message, e); }

        string modelId = !string.IsNullOrEmpty(resp.ModelId)
            ? resp.ModelId
            : (@params["modelId"]?.GetValue<string>() ?? "unknown");
        // Best-effort: model-specific bodies require user adapter to extract token counts.
        _execution.RecordStep(new StepInput
        {
            Tag = $"bedrock.invokeModel:{modelId}",
        });
        return resp;
    }

    private void CheckState()
    {
        var pre = _execution.Check();
        if (pre == StepOutcome.Locked) throw new MiddlewareException.Locked();
        if (pre == StepOutcome.Escalated && _opts.RaiseOnEscalation)
            throw new MiddlewareException.EscalationRaised();
    }
}

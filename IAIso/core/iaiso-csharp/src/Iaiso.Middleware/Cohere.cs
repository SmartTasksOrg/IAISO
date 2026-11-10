using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Core;

namespace Iaiso.Middleware.Cohere;

/// <summary>IAIso wrapper for Cohere chat.</summary>
public interface ICohereClient
{
    CohereResponse Chat(JsonObject @params);
}

public sealed class BilledUnits
{
    public long InputTokens { get; set; }
    public long OutputTokens { get; set; }
}

public sealed class CohereMeta
{
    public BilledUnits? Tokens { get; set; }
    public BilledUnits? BilledUnits { get; set; }
}

public sealed class CohereToolCall
{
    public string Name { get; }
    public CohereToolCall(string name) { Name = name; }
}

public sealed class CohereResponse
{
    public string Model { get; }
    public CohereMeta Meta { get; }
    public IReadOnlyList<CohereToolCall> ToolCalls { get; }
    public CohereResponse(string model, CohereMeta? meta, IReadOnlyList<CohereToolCall>? toolCalls)
    {
        Model = model;
        Meta = meta ?? new CohereMeta();
        ToolCalls = toolCalls ?? new List<CohereToolCall>();
    }
}

public sealed class CohereOptions
{
    public bool RaiseOnEscalation { get; set; }
    public static CohereOptions Defaults() => new();
}

public sealed class BoundedCohereClient
{
    private readonly ICohereClient _raw;
    private readonly BoundedExecution _execution;
    private readonly CohereOptions _opts;

    public BoundedCohereClient(ICohereClient raw, BoundedExecution execution, CohereOptions? opts = null)
    {
        _raw = raw;
        _execution = execution;
        _opts = opts ?? CohereOptions.Defaults();
    }

    public CohereResponse Chat(JsonObject @params)
    {
        var pre = _execution.Check();
        if (pre == StepOutcome.Locked) throw new MiddlewareException.Locked();
        if (pre == StepOutcome.Escalated && _opts.RaiseOnEscalation)
            throw new MiddlewareException.EscalationRaised();

        CohereResponse resp;
        try { resp = _raw.Chat(@params); }
        catch (System.Exception e) { throw new MiddlewareException.Provider(e.Message, e); }

        var b = resp.Meta.Tokens ?? resp.Meta.BilledUnits;
        long tokens = b is not null ? b.InputTokens + b.OutputTokens : 0;
        long toolCalls = resp.ToolCalls.Count;
        string model = string.IsNullOrEmpty(resp.Model) ? "unknown" : resp.Model;
        _execution.RecordStep(new StepInput
        {
            Tokens = tokens,
            ToolCalls = toolCalls,
            Tag = $"cohere.chat:{model}",
        });
        return resp;
    }
}

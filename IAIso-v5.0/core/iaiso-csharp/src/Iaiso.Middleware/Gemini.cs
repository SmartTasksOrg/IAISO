using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Core;

namespace Iaiso.Middleware.Gemini;

/// <summary>IAIso wrapper for Google Gemini / Vertex AI generative models.</summary>
public interface IGeminiModel
{
    GeminiResponse GenerateContent(JsonObject request);
    string ModelName { get; }
}

public sealed class UsageMetadata
{
    public long PromptTokenCount { get; set; }
    public long CandidatesTokenCount { get; set; }
    public long TotalTokenCount { get; set; }
}

public sealed class Part
{
    public bool HasFunctionCall { get; }
    public Part(bool hasFunctionCall) { HasFunctionCall = hasFunctionCall; }
}

public sealed class Candidate
{
    public IReadOnlyList<Part> Parts { get; }
    public Candidate(IReadOnlyList<Part>? parts) { Parts = parts ?? new List<Part>(); }
}

public sealed class GeminiResponse
{
    public UsageMetadata UsageMetadata { get; }
    public IReadOnlyList<Candidate> Candidates { get; }
    public GeminiResponse(UsageMetadata? um, IReadOnlyList<Candidate>? candidates)
    {
        UsageMetadata = um ?? new UsageMetadata();
        Candidates = candidates ?? new List<Candidate>();
    }
}

public sealed class GeminiOptions
{
    public bool RaiseOnEscalation { get; set; }
    public static GeminiOptions Defaults() => new();
}

public sealed class BoundedGeminiModel
{
    private readonly IGeminiModel _raw;
    private readonly BoundedExecution _execution;
    private readonly GeminiOptions _opts;

    public BoundedGeminiModel(IGeminiModel raw, BoundedExecution execution, GeminiOptions? opts = null)
    {
        _raw = raw;
        _execution = execution;
        _opts = opts ?? GeminiOptions.Defaults();
    }

    public GeminiResponse GenerateContent(JsonObject request)
    {
        var pre = _execution.Check();
        if (pre == StepOutcome.Locked) throw new MiddlewareException.Locked();
        if (pre == StepOutcome.Escalated && _opts.RaiseOnEscalation)
            throw new MiddlewareException.EscalationRaised();

        GeminiResponse resp;
        try { resp = _raw.GenerateContent(request); }
        catch (System.Exception e) { throw new MiddlewareException.Provider(e.Message, e); }

        long tokens = resp.UsageMetadata.TotalTokenCount;
        if (tokens == 0)
            tokens = resp.UsageMetadata.PromptTokenCount + resp.UsageMetadata.CandidatesTokenCount;
        long toolCalls = 0;
        foreach (var c in resp.Candidates)
            foreach (var p in c.Parts) if (p.HasFunctionCall) toolCalls++;
        string model = string.IsNullOrEmpty(_raw.ModelName) ? "unknown" : _raw.ModelName;
        _execution.RecordStep(new StepInput
        {
            Tokens = tokens,
            ToolCalls = toolCalls,
            Tag = $"gemini.generateContent:{model}",
        });
        return resp;
    }
}

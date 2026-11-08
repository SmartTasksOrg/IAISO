using Iaiso.Audit;

namespace Iaiso.Core;

/// <summary>Work unit accounted for in a single <c>Step()</c> call.</summary>
public sealed class StepInput
{
    public long Tokens { get; set; }
    public long ToolCalls { get; set; }
    public long Depth { get; set; }
    public string? Tag { get; set; }

    public static StepInput Empty => new();

    /// <summary>Throws when a count is negative: a negative count would lower pressure.
    /// Called by <see cref="PressureEngine.Step"/> on every step, because the
    /// properties are settable.</summary>
    public void Validate()
    {
        if (Tokens < 0) throw new ArgumentOutOfRangeException(nameof(Tokens), Tokens, "StepInput.Tokens must be >= 0");
        if (ToolCalls < 0) throw new ArgumentOutOfRangeException(nameof(ToolCalls), ToolCalls, "StepInput.ToolCalls must be >= 0");
        if (Depth < 0) throw new ArgumentOutOfRangeException(nameof(Depth), Depth, "StepInput.Depth must be >= 0");
    }

    /// <summary>Build from untrusted JSON (snake_case keys). Counts must be JSON
    /// integers >= 0; fractional, boolean, string and null values and unknown
    /// keys are refused.</summary>
    public static StepInput FromJson(System.Text.Json.JsonElement e)
    {
        if (e.ValueKind != System.Text.Json.JsonValueKind.Object)
            throw new ArgumentException("step input must be a JSON object");
        var w = new StepInput();
        foreach (var p in e.EnumerateObject())
        {
            switch (p.Name)
            {
                case "tokens": w.Tokens = Count(p); break;
                case "tool_calls": w.ToolCalls = Count(p); break;
                case "depth": w.Depth = Count(p); break;
                case "tag":
                    w.Tag = p.Value.ValueKind switch
                    {
                        System.Text.Json.JsonValueKind.Null => null,
                        System.Text.Json.JsonValueKind.String => p.Value.GetString(),
                        _ => throw new ArgumentException("StepInput.tag must be a string or null"),
                    };
                    break;
                default: throw new ArgumentException($"StepInput: unknown field {p.Name}");
            }
        }
        w.Validate();
        return w;
    }

    private static long Count(System.Text.Json.JsonProperty p)
    {
        if (p.Value.ValueKind != System.Text.Json.JsonValueKind.Number || !p.Value.TryGetInt64(out var n) || n < 0)
            throw new ArgumentException($"StepInput.{p.Name} must be a non-negative integer, got {p.Value.GetRawText()}");
        return n;
    }
}

/// <summary>Read-only view of pressure-engine state at a point in time.</summary>
public sealed record PressureSnapshot(
    double Pressure,
    long Step,
    Lifecycle Lifecycle,
    double LastDelta,
    double LastStepAt
);

/// <summary>Options for <see cref="PressureEngine"/>.</summary>
public sealed class EngineOptions
{
    public string ExecutionId { get; set; } = "exec-default";
    public ISink? AuditSink { get; set; }
    public IClock? Clock { get; set; }
    public IClock? TimestampClock { get; set; }
}

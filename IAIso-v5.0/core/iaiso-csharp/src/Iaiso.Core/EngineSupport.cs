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

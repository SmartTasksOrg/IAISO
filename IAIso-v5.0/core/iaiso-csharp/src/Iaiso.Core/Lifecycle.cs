namespace Iaiso.Core;

/// <summary>
/// The engine's high-level lifecycle state. Wire-format strings (returned
/// by <see cref="WireExtensions.Wire(Lifecycle)"/>) MUST match the Python,
/// Node, Go, Rust, and Java reference SDKs exactly.
/// </summary>
public enum Lifecycle
{
    Init,
    Running,
    Escalated,
    Released,
    Locked,
}

/// <summary>The result of a single <c>step()</c> call.</summary>
public enum StepOutcome
{
    Ok,
    Escalated,
    Released,
    Locked,
}

/// <summary>Wire-format helpers for cross-SDK string compatibility.</summary>
public static class WireExtensions
{
    public static string Wire(this Lifecycle l) => l switch
    {
        Lifecycle.Init => "init",
        Lifecycle.Running => "running",
        Lifecycle.Escalated => "escalated",
        Lifecycle.Released => "released",
        Lifecycle.Locked => "locked",
        _ => l.ToString().ToLowerInvariant(),
    };

    public static string Wire(this StepOutcome o) => o switch
    {
        StepOutcome.Ok => "ok",
        StepOutcome.Escalated => "escalated",
        StepOutcome.Released => "released",
        StepOutcome.Locked => "locked",
        _ => o.ToString().ToLowerInvariant(),
    };

    public static Lifecycle ParseLifecycle(string s) => s switch
    {
        "init" => Lifecycle.Init,
        "running" => Lifecycle.Running,
        "escalated" => Lifecycle.Escalated,
        "released" => Lifecycle.Released,
        "locked" => Lifecycle.Locked,
        _ => throw new System.ArgumentException($"unknown lifecycle: {s}"),
    };

    public static StepOutcome ParseStepOutcome(string s) => s switch
    {
        "ok" => StepOutcome.Ok,
        "escalated" => StepOutcome.Escalated,
        "released" => StepOutcome.Released,
        "locked" => StepOutcome.Locked,
        _ => throw new System.ArgumentException($"unknown step outcome: {s}"),
    };
}

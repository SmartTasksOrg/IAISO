using System;
using System.Collections.Generic;
using System.Threading;
using Iaiso.Audit;

namespace Iaiso.Core;

/// <summary>Options for <see cref="BoundedExecution.Start"/>.</summary>
public sealed class BoundedExecutionOptions
{
    public string? ExecutionId { get; set; }
    public PressureConfig Config { get; set; } = PressureConfig.Defaults();
    public ISink? AuditSink { get; set; }
    public IClock? Clock { get; set; }
    public IClock? TimestampClock { get; set; }
}

/// <summary>
/// High-level execution facade. Composes a <see cref="PressureEngine"/>
/// with an audit sink and lifecycle management.
/// </summary>
/// <remarks>
/// Use <see cref="Run(BoundedExecutionOptions, Action{BoundedExecution})"/>
/// for the closure style with automatic cleanup, or <see cref="Start"/>
/// + <c>using</c> for explicit lifecycle control:
/// <code>
/// using var exec = BoundedExecution.Start(opts);
/// exec.RecordToolCall("search", 500);
/// </code>
/// </remarks>
public sealed class BoundedExecution : IDisposable
{
    private readonly PressureEngine _engine;
    private readonly ISink _auditSink;
    private readonly IClock _timestampClock;
    private int _closed; // 0 == open, 1 == closed (atomic transitions)

    private BoundedExecution(BoundedExecutionOptions opts)
    {
        var execId = opts.ExecutionId;
        if (string.IsNullOrEmpty(execId))
        {
            execId = "exec-" + System.Diagnostics.Stopwatch.GetTimestamp().ToString("x");
        }
        var clk = opts.Clock ?? WallClock.Instance;
        var tsClk = opts.TimestampClock ?? clk;
        _auditSink = opts.AuditSink ?? NullSink.Instance;
        _timestampClock = tsClk;
        _engine = new PressureEngine(opts.Config, new EngineOptions
        {
            ExecutionId = execId,
            AuditSink = _auditSink,
            Clock = clk,
            TimestampClock = tsClk,
        });
    }

    /// <summary>Construct a <see cref="BoundedExecution"/>. Caller MUST <see cref="Dispose"/>.</summary>
    public static BoundedExecution Start(BoundedExecutionOptions opts) => new(opts);

    /// <summary>Run a closure inside a bounded execution; closes on exit.</summary>
    public static void Run(BoundedExecutionOptions opts, Action<BoundedExecution> body)
    {
        bool errored = false;
        BoundedExecution? exec = null;
        try
        {
            exec = Start(opts);
            body(exec);
        }
        catch
        {
            errored = true;
            throw;
        }
        finally
        {
            exec?.CloseWith(errored);
        }
    }

    public PressureEngine Engine => _engine;
    public PressureSnapshot Snapshot() => _engine.Snapshot();

    /// <summary>Account for tokens with an optional tag.</summary>
    public StepOutcome RecordTokens(long tokens, string? tag = null) =>
        _engine.Step(new StepInput { Tokens = tokens, Tag = tag });

    /// <summary>Account for a single tool invocation.</summary>
    public StepOutcome RecordToolCall(string name, long tokens) =>
        _engine.Step(new StepInput { Tokens = tokens, ToolCalls = 1, Tag = name });

    /// <summary>General step accounting.</summary>
    public StepOutcome RecordStep(StepInput work) => _engine.Step(work);

    /// <summary>Pre-check the engine state without advancing it.</summary>
    public StepOutcome Check() => _engine.Lifecycle switch
    {
        Lifecycle.Locked => StepOutcome.Locked,
        Lifecycle.Escalated => StepOutcome.Escalated,
        _ => StepOutcome.Ok,
    };

    public PressureSnapshot Reset() => _engine.Reset();

    public void Dispose() => CloseWith(false);

    internal void CloseWith(bool errored)
    {
        if (Interlocked.CompareExchange(ref _closed, 1, 0) != 0) return;
        var snap = _engine.Snapshot();
        var data = new SortedDictionary<string, object?>
        {
            ["final_pressure"] = snap.Pressure,
            ["final_lifecycle"] = snap.Lifecycle.Wire(),
            ["exception"] = errored ? "error" : null,
        };
        _auditSink.Emit(new Event(_engine.ExecutionId, "execution.closed",
            _timestampClock.Now(), data));
    }
}

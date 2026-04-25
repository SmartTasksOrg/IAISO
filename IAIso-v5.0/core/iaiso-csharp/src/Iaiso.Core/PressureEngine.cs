using System.Collections.Generic;
using Iaiso.Audit;

namespace Iaiso.Core;

/// <summary>
/// The IAIso pressure engine. Thread-safe; <c>Step()</c> may be called
/// from multiple threads, though semantically each execution should be
/// driven by a single thread. See <c>spec/pressure/README.md</c> for
/// normative semantics.
/// </summary>
public sealed class PressureEngine
{
    private readonly PressureConfig _cfg;
    private readonly string _executionId;
    private readonly ISink _audit;
    private readonly IClock _clock;
    private readonly IClock _timestampClock;
    private readonly object _lock = new();

    // mutable state guarded by `_lock`
    private double _pressure;
    private long _step;
    private Lifecycle _lifecycle;
    private double _lastDelta;
    private double _lastStepAt;

    public PressureEngine(PressureConfig cfg, EngineOptions opts)
    {
        cfg.Validate();
        _cfg = cfg;
        _executionId = opts.ExecutionId;
        _audit = opts.AuditSink ?? NullSink.Instance;
        _clock = opts.Clock ?? WallClock.Instance;
        _timestampClock = opts.TimestampClock ?? _clock;
        _pressure = 0.0;
        _step = 0;
        _lifecycle = Lifecycle.Init;
        _lastDelta = 0.0;
        _lastStepAt = _clock.Now();

        var data = new SortedDictionary<string, object?> { ["pressure"] = 0.0 };
        Emit("engine.init", data);
    }

    public PressureConfig Config => _cfg;
    public string ExecutionId => _executionId;

    public double Pressure
    {
        get { lock (_lock) { return _pressure; } }
    }

    public Lifecycle Lifecycle
    {
        get { lock (_lock) { return _lifecycle; } }
    }

    public PressureSnapshot Snapshot()
    {
        lock (_lock)
        {
            return new PressureSnapshot(_pressure, _step, _lifecycle, _lastDelta, _lastStepAt);
        }
    }

    /// <summary>Account for a unit of work; advance the engine.</summary>
    public StepOutcome Step(StepInput work)
    {
        lock (_lock)
        {
            if (_lifecycle == Lifecycle.Locked)
            {
                var rejected = new SortedDictionary<string, object?>
                {
                    ["reason"] = "locked",
                    ["requested_tokens"] = work.Tokens,
                    ["requested_tools"] = work.ToolCalls,
                };
                Emit("engine.step.rejected", rejected);
                return StepOutcome.Locked;
            }

            double now = _clock.Now();
            double elapsed = System.Math.Max(0.0, now - _lastStepAt);

            double delta = (work.Tokens / 1000.0) * _cfg.TokenCoefficient
                + work.ToolCalls * _cfg.ToolCoefficient
                + work.Depth * _cfg.DepthCoefficient;
            double decay = _cfg.DissipationPerStep + elapsed * _cfg.DissipationPerSecond;

            double newPressure = Clamp01(_pressure + delta - decay);
            _pressure = newPressure;
            _step += 1;
            _lastDelta = delta - decay;
            _lastStepAt = now;
            _lifecycle = Lifecycle.Running;

            var stepData = new SortedDictionary<string, object?>
            {
                ["step"] = _step,
                ["pressure"] = _pressure,
                ["delta"] = delta,
                ["decay"] = decay,
                ["tokens"] = work.Tokens,
                ["tool_calls"] = work.ToolCalls,
                ["depth"] = work.Depth,
                ["tag"] = work.Tag,
            };

            double pressureNow = _pressure;
            double releaseThr = _cfg.ReleaseThreshold;
            double escThr = _cfg.EscalationThreshold;
            bool postReleaseLock = _cfg.PostReleaseLock;

            Emit("engine.step", stepData);

            if (pressureNow >= releaseThr)
            {
                var rd = new SortedDictionary<string, object?>
                {
                    ["pressure"] = pressureNow,
                    ["threshold"] = releaseThr,
                };
                Emit("engine.release", rd);
                _pressure = 0.0;
                if (postReleaseLock)
                {
                    _lifecycle = Lifecycle.Locked;
                    var ld = new SortedDictionary<string, object?>
                    {
                        ["reason"] = "post_release_lock",
                    };
                    Emit("engine.locked", ld);
                }
                else
                {
                    _lifecycle = Lifecycle.Running;
                }
                return StepOutcome.Released;
            }
            if (pressureNow >= escThr)
            {
                _lifecycle = Lifecycle.Escalated;
                var ed = new SortedDictionary<string, object?>
                {
                    ["pressure"] = pressureNow,
                    ["threshold"] = escThr,
                };
                Emit("engine.escalation", ed);
                return StepOutcome.Escalated;
            }
            return StepOutcome.Ok;
        }
    }

    /// <summary>Reset the engine. Emits <c>engine.reset</c>.</summary>
    public PressureSnapshot Reset()
    {
        lock (_lock)
        {
            _pressure = 0.0;
            _step = 0;
            _lastDelta = 0.0;
            _lastStepAt = _clock.Now();
            _lifecycle = Lifecycle.Init;
            var data = new SortedDictionary<string, object?> { ["pressure"] = 0.0 };
            Emit("engine.reset", data);
            return new PressureSnapshot(_pressure, _step, _lifecycle, _lastDelta, _lastStepAt);
        }
    }

    private void Emit(string kind, IDictionary<string, object?> data)
    {
        _audit.Emit(new Event(_executionId, kind, _timestampClock.Now(),
            new SortedDictionary<string, object?>(data)));
    }

    private static double Clamp01(double v)
    {
        if (v < 0.0) return 0.0;
        if (v > 1.0) return 1.0;
        return v;
    }
}

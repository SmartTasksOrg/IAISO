using System;
using System.Collections.Generic;
using Iaiso.Audit;
using Iaiso.Policy;

namespace Iaiso.Coordination;

/// <summary>
/// In-memory coordinator that aggregates pressure across a single
/// process's executions.
/// </summary>
public class SharedPressureCoordinator
{
    private readonly string _coordinatorId;
    private readonly double _escalationThreshold;
    private readonly double _releaseThreshold;
    private readonly double _notifyCooldownSeconds;
    private readonly IAggregator _aggregator;
    private readonly ISink _auditSink;
    private readonly Action<Snapshot>? _onEscalation;
    private readonly Action<Snapshot>? _onRelease;
    private readonly ICoordClock _clock;
    private readonly object _lock = new();

    private readonly SortedDictionary<string, double> _pressures = new();
    private CoordinatorLifecycle _lifecycle = CoordinatorLifecycle.Nominal;
    private double _lastNotifyAt;

    internal SharedPressureCoordinator(string coordinatorId, double escalationThreshold,
                                       double releaseThreshold, double notifyCooldownSeconds,
                                       IAggregator aggregator, ISink auditSink,
                                       Action<Snapshot>? onEscalation,
                                       Action<Snapshot>? onRelease,
                                       ICoordClock clock,
                                       bool emitInit)
    {
        if (releaseThreshold <= escalationThreshold)
        {
            throw new CoordinatorException(
                $"release_threshold must exceed escalation_threshold ({releaseThreshold} <= {escalationThreshold})");
        }
        _coordinatorId = coordinatorId;
        _escalationThreshold = escalationThreshold;
        _releaseThreshold = releaseThreshold;
        _notifyCooldownSeconds = notifyCooldownSeconds;
        _aggregator = aggregator;
        _auditSink = auditSink ?? NullSink.Instance;
        _onEscalation = onEscalation;
        _onRelease = onRelease;
        _clock = clock;
        if (emitInit) EmitInit("memory");
    }

    public static Builder CreateBuilder() => new();

    public string CoordinatorId => _coordinatorId;
    public IAggregator Aggregator => _aggregator;

    public Snapshot Register(string executionId)
    {
        lock (_lock) { _pressures[executionId] = 0.0; }
        Emit("coordinator.execution_registered",
            new SortedDictionary<string, object?> { ["execution_id"] = executionId });
        return Snapshot();
    }

    public Snapshot Unregister(string executionId)
    {
        lock (_lock) { _pressures.Remove(executionId); }
        Emit("coordinator.execution_unregistered",
            new SortedDictionary<string, object?> { ["execution_id"] = executionId });
        return Snapshot();
    }

    /// <summary>Update pressure for an execution and re-evaluate lifecycle.</summary>
    public Snapshot Update(string executionId, double pressure)
    {
        if (pressure < 0.0 || pressure > 1.0)
            throw new CoordinatorException($"pressure must be in [0, 1], got {pressure}");
        lock (_lock) { _pressures[executionId] = pressure; }
        return Evaluate();
    }

    public int Reset()
    {
        int count;
        lock (_lock)
        {
            count = _pressures.Count;
            foreach (var k in new List<string>(_pressures.Keys)) _pressures[k] = 0.0;
            _lifecycle = CoordinatorLifecycle.Nominal;
        }
        Emit("coordinator.reset",
            new SortedDictionary<string, object?> { ["fleet_size"] = count });
        return count;
    }

    public Snapshot Snapshot()
    {
        lock (_lock)
        {
            double agg = _aggregator.Aggregate(_pressures);
            return new Snapshot(_coordinatorId, agg, _lifecycle,
                _pressures.Count, new Dictionary<string, double>(_pressures));
        }
    }

    /// <summary>Replace per-execution pressures wholesale. Used by Redis variant.</summary>
    internal void SetPressuresFromMap(IReadOnlyDictionary<string, double> updated)
    {
        lock (_lock)
        {
            _pressures.Clear();
            foreach (var kv in updated) _pressures[kv.Key] = kv.Value;
        }
    }

    internal Snapshot Evaluate()
    {
        double now = _clock.Now();
        double agg;
        CoordinatorLifecycle prior;
        CoordinatorLifecycle next;
        bool inCooldown;
        lock (_lock)
        {
            agg = _aggregator.Aggregate(_pressures);
            prior = _lifecycle;
            inCooldown = (now - _lastNotifyAt) < _notifyCooldownSeconds;
            if (agg >= _releaseThreshold) next = CoordinatorLifecycle.Released;
            else if (agg >= _escalationThreshold)
                next = prior == CoordinatorLifecycle.Nominal
                    ? CoordinatorLifecycle.Escalated
                    : prior;
            else next = CoordinatorLifecycle.Nominal;
            _lifecycle = next;
        }
        if (next != prior && !inCooldown)
        {
            switch (next)
            {
                case CoordinatorLifecycle.Released:
                    Emit("coordinator.release",
                        new SortedDictionary<string, object?>
                        {
                            ["aggregate_pressure"] = agg,
                            ["threshold"] = _releaseThreshold,
                        });
                    SetLastNotifyAt(now);
                    _onRelease?.Invoke(Snapshot());
                    break;
                case CoordinatorLifecycle.Escalated:
                    Emit("coordinator.escalation",
                        new SortedDictionary<string, object?>
                        {
                            ["aggregate_pressure"] = agg,
                            ["threshold"] = _escalationThreshold,
                        });
                    SetLastNotifyAt(now);
                    _onEscalation?.Invoke(Snapshot());
                    break;
                case CoordinatorLifecycle.Nominal:
                    Emit("coordinator.returned_to_nominal",
                        new SortedDictionary<string, object?>
                        {
                            ["aggregate_pressure"] = agg,
                        });
                    SetLastNotifyAt(now);
                    break;
            }
        }
        return Snapshot();
    }

    private void SetLastNotifyAt(double t) { lock (_lock) { _lastNotifyAt = t; } }

    private void EmitInit(string backend)
    {
        Emit("coordinator.init", new SortedDictionary<string, object?>
        {
            ["coordinator_id"] = _coordinatorId,
            ["aggregator"] = _aggregator.Name,
            ["backend"] = backend,
        });
    }

    internal void Emit(string kind, IDictionary<string, object?> data)
    {
        var ev = new Event($"coord:{_coordinatorId}", kind, _clock.Now(),
            new SortedDictionary<string, object?>(data));
        _auditSink.Emit(ev);
    }

    public sealed class Builder
    {
        public string CoordinatorId { get; set; } = "default";
        public double EscalationThreshold { get; set; } = 5.0;
        public double ReleaseThreshold { get; set; } = 8.0;
        public double NotifyCooldownSeconds { get; set; } = 1.0;
        public IAggregator Aggregator { get; set; } = new SumAggregator();
        public ISink? AuditSink { get; set; }
        public Action<Snapshot>? OnEscalation { get; set; }
        public Action<Snapshot>? OnRelease { get; set; }
        public ICoordClock? Clock { get; set; }

        public Builder WithCoordinatorId(string v) { CoordinatorId = v; return this; }
        public Builder WithEscalationThreshold(double v) { EscalationThreshold = v; return this; }
        public Builder WithReleaseThreshold(double v) { ReleaseThreshold = v; return this; }
        public Builder WithNotifyCooldownSeconds(double v) { NotifyCooldownSeconds = v; return this; }
        public Builder WithAggregator(IAggregator v) { Aggregator = v; return this; }
        public Builder WithAuditSink(ISink v) { AuditSink = v; return this; }
        public Builder WithOnEscalation(Action<Snapshot> v) { OnEscalation = v; return this; }
        public Builder WithOnRelease(Action<Snapshot> v) { OnRelease = v; return this; }
        public Builder WithClock(ICoordClock v) { Clock = v; return this; }

        public SharedPressureCoordinator Build() =>
            new(CoordinatorId, EscalationThreshold, ReleaseThreshold,
                NotifyCooldownSeconds, Aggregator, AuditSink ?? NullSink.Instance,
                OnEscalation, OnRelease, Clock ?? CoordWallClock.Instance, true);
    }
}

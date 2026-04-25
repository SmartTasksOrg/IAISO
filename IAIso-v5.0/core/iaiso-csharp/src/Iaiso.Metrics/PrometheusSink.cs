using Iaiso.Audit;

namespace Iaiso.Metrics;

/// <summary>
/// IAIso Prometheus metrics sink. Structurally typed — this module
/// doesn't depend on any specific Prometheus client library. The
/// <c>prometheus-net</c> and OpenMetrics-compatible libraries satisfy
/// these interfaces with thin adapters.
/// </summary>
public sealed class PrometheusSink : ISink
{
    /// <summary>Suggested histogram buckets for <c>iaiso_step_delta</c>.</summary>
    public static readonly double[] SuggestedHistogramBuckets =
        { 0.0, 0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0 };

    public interface ICounter { void Inc(); }
    public interface ICounterVec { ICounter Labels(params string[] values); }
    public interface IGauge { void Set(double v); }
    public interface IGaugeVec { IGauge Labels(params string[] values); }
    public interface IHistogram { void Observe(double v); }

    private readonly ICounterVec? _events;
    private readonly ICounter? _escalations;
    private readonly ICounter? _releases;
    private readonly IGaugeVec? _pressure;
    private readonly IHistogram? _stepDelta;

    public PrometheusSink(ICounterVec? events, ICounter? escalations, ICounter? releases,
                          IGaugeVec? pressure, IHistogram? stepDelta)
    {
        _events = events;
        _escalations = escalations;
        _releases = releases;
        _pressure = pressure;
        _stepDelta = stepDelta;
    }

    public void Emit(Event @event)
    {
        _events?.Labels(@event.Kind).Inc();
        switch (@event.Kind)
        {
            case "engine.escalation":
                _escalations?.Inc();
                break;
            case "engine.release":
                _releases?.Inc();
                break;
            case "engine.step":
                if (@event.Data.TryGetValue("pressure", out var p) && p is double pd)
                    _pressure?.Labels(@event.ExecutionId).Set(pd);
                if (@event.Data.TryGetValue("delta", out var d) && d is double dd)
                    _stepDelta?.Observe(dd);
                break;
        }
    }
}

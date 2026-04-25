using System.Collections.Concurrent;
using System.Collections.Generic;
using Iaiso.Audit;

namespace Iaiso.Observability;

/// <summary>
/// IAIso OpenTelemetry tracing sink. Structurally typed against the
/// OTel trace API. The official <c>OpenTelemetry.Api</c>
/// <c>Tracer</c> and <c>Span</c> satisfy these interfaces with thin
/// adapters.
/// </summary>
public sealed class OtelSpanSink : ISink
{
    public interface ISpan
    {
        void AddEvent(string name, IReadOnlyDictionary<string, object?> attributes);
        void SetAttribute(string key, object value);
        void End();
    }

    public interface ITracer
    {
        ISpan StartSpan(string name, IReadOnlyDictionary<string, object?> attributes);
    }

    private readonly ITracer _tracer;
    private readonly string _spanName;
    private readonly ConcurrentDictionary<string, ISpan> _spans = new();

    public OtelSpanSink(ITracer tracer, string? spanName = null)
    {
        _tracer = tracer;
        _spanName = string.IsNullOrEmpty(spanName) ? "iaiso.execution" : spanName;
    }

    /// <summary>End any open spans. Useful at shutdown.</summary>
    public void CloseAll()
    {
        foreach (var s in _spans.Values)
        {
            try { s.End(); } catch { /* best-effort */ }
        }
        _spans.Clear();
    }

    public void Emit(Event @event)
    {
        ISpan? span;
        if (@event.Kind == "engine.init")
        {
            var attrs = new Dictionary<string, object?> { ["iaiso.execution_id"] = @event.ExecutionId };
            span = _tracer.StartSpan($"{_spanName}:{@event.ExecutionId}", attrs);
            _spans[@event.ExecutionId] = span;
        }
        else
        {
            _spans.TryGetValue(@event.ExecutionId, out span);
        }
        if (span is null) return;

        var evAttrs = new Dictionary<string, object?>(@event.Data)
        {
            ["iaiso.schema_version"] = @event.SchemaVersion,
        };
        span.AddEvent(@event.Kind, evAttrs);

        switch (@event.Kind)
        {
            case "engine.step":
                if (@event.Data.TryGetValue("pressure", out var p) && p is not null)
                    span.SetAttribute("iaiso.pressure", p);
                break;
            case "engine.escalation":
                span.SetAttribute("iaiso.escalated", true);
                break;
            case "engine.release":
                span.SetAttribute("iaiso.released", true);
                break;
            case "execution.closed":
                span.End();
                _spans.TryRemove(@event.ExecutionId, out _);
                break;
        }
    }
}

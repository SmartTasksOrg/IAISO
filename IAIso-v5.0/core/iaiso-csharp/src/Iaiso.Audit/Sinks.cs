using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;

namespace Iaiso.Audit;

/// <summary>
/// The interface every audit sink implements. Implementations SHOULD
/// make <see cref="Emit"/> non-blocking on the agent's hot path —
/// sustained backpressure is signaled by dropping rather than throwing.
/// See <c>spec/events/README.md §6</c> for normative delivery semantics.
/// </summary>
public interface ISink
{
    void Emit(Event @event);
}

/// <summary>A sink that records emitted events in memory. Useful for tests.</summary>
public sealed class MemorySink : ISink
{
    private readonly object _lock = new();
    private readonly List<Event> _events = new();

    public void Emit(Event @event)
    {
        lock (_lock) { _events.Add(@event); }
    }

    public IReadOnlyList<Event> Events()
    {
        lock (_lock) { return _events.ToArray(); }
    }

    public void Clear()
    {
        lock (_lock) { _events.Clear(); }
    }
}

/// <summary>A sink that discards every event.</summary>
public sealed class NullSink : ISink
{
    public static readonly NullSink Instance = new();
    private NullSink() {}
    public void Emit(Event @event) { /* no-op */ }
}

/// <summary>A sink that writes one JSON event per line to <see cref="Console.Out"/>.</summary>
public sealed class StdoutSink : ISink
{
    public static readonly StdoutSink Instance = new();
    private StdoutSink() {}
    public void Emit(Event @event) => Console.Out.WriteLine(@event.ToJson());
}

/// <summary>A sink that broadcasts every event to a list of children.</summary>
public sealed class FanoutSink : ISink
{
    private readonly ISink[] _sinks;
    public FanoutSink(params ISink[] sinks) { _sinks = sinks; }
    public IReadOnlyList<ISink> Sinks => _sinks;

    public void Emit(Event @event)
    {
        foreach (var s in _sinks) { s.Emit(@event); }
    }
}

/// <summary>
/// A sink that appends one JSON event per line to a file. Errors are
/// silently dropped — best-effort delivery semantics specified in
/// <c>spec/events/README.md §6</c>.
/// </summary>
public sealed class JsonlFileSink : ISink
{
    private readonly string _path;
    private readonly object _lock = new();

    public JsonlFileSink(string path) { _path = path; }

    public void Emit(Event @event)
    {
        lock (_lock)
        {
            try
            {
                File.AppendAllText(_path, @event.ToJson() + "\n");
            }
            catch (IOException) { /* best-effort */ }
            catch (UnauthorizedAccessException) { /* best-effort */ }
        }
    }
}

using System;

namespace Iaiso.Coordination;

/// <summary>Lifecycle state of a fleet-aggregated coordinator.</summary>
public enum CoordinatorLifecycle
{
    Nominal,
    Escalated,
    Released,
}

public static class CoordinatorLifecycleExtensions
{
    public static string Wire(this CoordinatorLifecycle l) => l switch
    {
        CoordinatorLifecycle.Nominal => "nominal",
        CoordinatorLifecycle.Escalated => "escalated",
        CoordinatorLifecycle.Released => "released",
        _ => l.ToString().ToLowerInvariant(),
    };
}

public class CoordinatorException : Exception
{
    public CoordinatorException(string message) : base(message) {}
    public CoordinatorException(string message, Exception inner) : base(message, inner) {}
}

/// <summary>A clock returning fractional seconds for the coordinator.</summary>
public interface ICoordClock
{
    double Now();
}

public sealed class CoordWallClock : ICoordClock
{
    public static readonly CoordWallClock Instance = new();
    public double Now() => (DateTimeOffset.UtcNow - DateTimeOffset.UnixEpoch).TotalSeconds;
}

public sealed class DelegateCoordClock : ICoordClock
{
    private readonly Func<double> _fn;
    public DelegateCoordClock(Func<double> fn) { _fn = fn; }
    public double Now() => _fn();
}

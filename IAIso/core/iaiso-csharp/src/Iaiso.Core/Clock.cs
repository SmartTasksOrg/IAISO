using System;

namespace Iaiso.Core;

/// <summary>
/// A clock returning fractional seconds. Tests pass scripted clocks
/// for deterministic evaluation.
/// </summary>
public interface IClock
{
    double Now();
}

/// <summary>A wallclock based on <see cref="DateTimeOffset.UtcNow"/>.</summary>
public sealed class WallClock : IClock
{
    public static readonly WallClock Instance = new();
    public double Now() => (DateTimeOffset.UtcNow - DateTimeOffset.UnixEpoch).TotalSeconds;
}

/// <summary>
/// A scripted clock that returns the next value from a sequence on each
/// call. After the sequence is exhausted, the last value is returned
/// repeatedly. Useful for conformance vectors.
/// </summary>
public sealed class ScriptedClock : IClock
{
    private readonly double[] _seq;
    private int _idx;

    public ScriptedClock(params double[] seq) { _seq = seq; }
    public ScriptedClock(System.Collections.Generic.IEnumerable<double> seq)
        : this(System.Linq.Enumerable.ToArray(seq)) {}

    public double Now()
    {
        if (_seq.Length == 0) return 0.0;
        if (_idx < _seq.Length)
        {
            return _seq[_idx++];
        }
        return _seq[_seq.Length - 1];
    }
}

/// <summary>An <see cref="IClock"/> backed by a delegate.</summary>
public sealed class DelegateClock : IClock
{
    private readonly Func<double> _fn;
    public DelegateClock(Func<double> fn) { _fn = fn; }
    public double Now() => _fn();
}

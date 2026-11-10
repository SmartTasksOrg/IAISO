using System.Collections.Generic;
using System.IO;

namespace Iaiso.Conformance;

/// <summary>Result of running one vector.</summary>
public sealed class VectorResult
{
    public string Section { get; }
    public string Name { get; }
    public bool Passed { get; }
    public string Message { get; }

    public VectorResult(string section, string name, bool passed, string message)
    {
        Section = section;
        Name = name;
        Passed = passed;
        Message = message;
    }

    public static VectorResult Pass(string section, string name) =>
        new(section, name, true, "");
    public static VectorResult Fail(string section, string name, string message) =>
        new(section, name, false, message);
}

/// <summary>Results aggregated by section.</summary>
public sealed class SectionResults
{
    public List<VectorResult> Pressure { get; } = new();
    public List<VectorResult> Consent { get; } = new();
    public List<VectorResult> Events { get; } = new();
    public List<VectorResult> Policy { get; } = new();

    public int CountPassed()
    {
        int p = 0;
        foreach (var b in new[] { Pressure, Consent, Events, Policy })
            foreach (var r in b) if (r.Passed) p++;
        return p;
    }

    public int CountTotal() =>
        Pressure.Count + Consent.Count + Events.Count + Policy.Count;
}

/// <summary>Top-level conformance runner.</summary>
public static class ConformanceRunner
{
    /// <summary>Absolute tolerance for floating-point comparisons.</summary>
    public const double Tolerance = 1e-9;

    /// <summary>Run every section against the spec at <paramref name="specRoot"/>.</summary>
    public static SectionResults RunAll(string specRoot)
    {
        var s = new SectionResults();
        s.Pressure.AddRange(PressureRunner.Run(specRoot));
        s.Consent.AddRange(ConsentRunner.Run(specRoot));
        s.Events.AddRange(EventsRunner.Run(specRoot));
        s.Policy.AddRange(PolicyRunner.Run(specRoot));
        return s;
    }
}

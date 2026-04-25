using System.IO;
using Iaiso.Conformance;

namespace Iaiso.Tests;

public sealed class ConformanceSuiteTests
{
    private static string SpecRoot()
    {
        // Tests run from tests/Iaiso.Tests/bin/Debug/net8.0/. Spec is at the repo root.
        var candidates = new[]
        {
            Path.Combine(Directory.GetCurrentDirectory(), "spec"),
            Path.Combine(Directory.GetCurrentDirectory(), "..", "..", "..", "..", "..", "spec"),
            "/home/claude/iaiso-csharp/spec",
        };
        foreach (var c in candidates)
            if (Directory.Exists(c)) return c;
        return "spec";
    }

    public void TestAllVectorsPass()
    {
        var r = ConformanceRunner.RunAll(SpecRoot());
        var failures = new System.Collections.Generic.List<string>();
        foreach (var bucket in new[] { r.Pressure, r.Consent, r.Events, r.Policy })
        {
            foreach (var v in bucket)
                if (!v.Passed) failures.Add($"[{v.Section}] {v.Name}: {v.Message}");
        }
        Assert.Equal(67, r.CountTotal());
        if (failures.Count > 0)
        {
            throw new AssertionException(
                $"conformance {r.CountPassed()}/{r.CountTotal()} - failures: " +
                string.Join("; ", failures));
        }
    }
}

using System.Text.Json;
using Iaiso.Audit;
using Iaiso.Core;

namespace Iaiso.Tests;

/// <summary>spec/pressure/hostile.json is shared by every IAIso port.
/// Built and run with .NET SDK 8.0.133 in the review (53/53 tests).</summary>
public sealed class HostileVectorsTests
{
    private static JsonElement Hostile()
    {
        foreach (var root in new[]
                 {
                     Path.Combine(Directory.GetCurrentDirectory(), "spec"),
                     Path.Combine(Directory.GetCurrentDirectory(), "..", "..", "..", "..", "..", "spec"),
                 })
        {
            var p = Path.Combine(root, "pressure", "hostile.json");
            if (File.Exists(p)) return JsonDocument.Parse(File.ReadAllText(p)).RootElement;
        }
        throw new InvalidOperationException("hostile.json not found");
    }

    private static PressureEngine Engine() => new(PressureConfig.Defaults(), new EngineOptions
    {
        ExecutionId = "hostile",
        AuditSink = new MemorySink(),
        Clock = new ScriptedClock(0.0),
    });

    public void TestHostileValuesAreRefused()
    {
        foreach (var v in Hostile().GetProperty("reject").EnumerateArray())
        {
            var json = "{\"" + v.GetProperty("field").GetString() + "\":" + v.GetProperty("value").GetRawText() + "}";
            var step = JsonDocument.Parse(json).RootElement;
            Assert.Throws<ArgumentException>(() => Engine().Step(StepInput.FromJson(step)),
                v.GetProperty("name").GetString());
        }
    }

    public void TestSettersCannotSmuggleNegatives()
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => Engine().Step(new StepInput { Tokens = -40000 }));
    }

    public void TestExtremeValuesAreHandled()
    {
        foreach (var v in Hostile().GetProperty("accept").EnumerateArray())
        {
            var e = Engine();
            var outcome = e.Step(StepInput.FromJson(v.GetProperty("step")));
            var exp = v.GetProperty("expect");
            var name = v.GetProperty("name").GetString();
            Assert.False(double.IsNaN(e.Pressure), name);
            Assert.EqualDouble(exp.GetProperty("pressure").GetDouble(), e.Pressure, 1e-9, name);
            Assert.Equal(exp.GetProperty("outcome").GetString(), outcome.Wire(), name);
            Assert.Equal(exp.GetProperty("lifecycle").GetString(), e.Lifecycle.Wire(), name);
        }
    }
}

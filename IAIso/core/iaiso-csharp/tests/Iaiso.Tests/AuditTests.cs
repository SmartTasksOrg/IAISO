using System.Collections.Generic;
using Iaiso.Audit;

namespace Iaiso.Tests;

public sealed class AuditTests
{
    public void TestEventToJsonStableKeyOrder()
    {
        var data = new SortedDictionary<string, object?>
        {
            ["zeta"] = 1L,
            ["alpha"] = "a",
            ["beta"] = true,
        };
        var ev = new Event("exec-1", "test.kind", 1700000000.0, data);
        string json = ev.ToJson();
        // Top-level keys must be in spec order
        Assert.True(json.IndexOf("schema_version") < json.IndexOf("execution_id"));
        Assert.True(json.IndexOf("execution_id") < json.IndexOf("kind"));
        Assert.True(json.IndexOf("kind") < json.IndexOf("timestamp"));
        Assert.True(json.IndexOf("timestamp") < json.IndexOf("data"));
        // Data keys alphabetical
        Assert.True(json.IndexOf("alpha") < json.IndexOf("beta"));
        Assert.True(json.IndexOf("beta") < json.IndexOf("zeta"));
    }

    public void TestIntegerDoublesSerializeAsIntegers()
    {
        var data = new SortedDictionary<string, object?> { ["pressure"] = 0.0 };
        var ev = new Event("e", "k", 1700000000.0, data);
        string json = ev.ToJson();
        Assert.Contains("\"pressure\":0", json);
        Assert.False(json.Contains("\"pressure\":0.0"), $"expected 0 not 0.0 in: {json}");
        Assert.Contains("\"timestamp\":1700000000", json);
    }

    public void TestMemorySinkRecordsEvents()
    {
        var sink = new MemorySink();
        sink.Emit(new Event("e1", "k1", 0, null));
        sink.Emit(new Event("e2", "k2", 1, null));
        Assert.Equal(2, sink.Events().Count);
    }

    public void TestNullSinkAcceptsEverything()
    {
        NullSink.Instance.Emit(new Event("e", "k", 0, null));
        // No exception, no state — nothing to assert beyond no-throw.
        Assert.True(true);
    }

    public void TestFanoutSinkBroadcasts()
    {
        var a = new MemorySink();
        var b = new MemorySink();
        var fan = new FanoutSink(a, b);
        fan.Emit(new Event("e", "k", 0, null));
        Assert.Equal(1, a.Events().Count);
        Assert.Equal(1, b.Events().Count);
    }

    public void TestSchemaVersionConstant()
    {
        Assert.Equal("1.0", Event.CurrentSchemaVersion);
    }
}

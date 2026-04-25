using System.Collections.Generic;
using Iaiso.Audit;
using Iaiso.Coordination;
using Iaiso.Policy;

namespace Iaiso.Tests;

public sealed class CoordinationTests
{
    public void TestAggregatesSum()
    {
        var c = SharedPressureCoordinator.CreateBuilder()
            .WithAuditSink(new MemorySink())
            .WithClock(new DelegateCoordClock(() => 0.0))
            .Build();
        c.Register("a");
        c.Register("b");
        c.Update("a", 0.3);
        var snap = c.Update("b", 0.5);
        Assert.EqualDouble(0.8, snap.AggregatePressure);
    }

    public void TestEscalationCallbackFires()
    {
        int calls = 0;
        var c = SharedPressureCoordinator.CreateBuilder()
            .WithEscalationThreshold(0.7)
            .WithReleaseThreshold(0.95)
            .WithNotifyCooldownSeconds(0.0)
            .WithClock(new DelegateCoordClock(() => 0.0))
            .WithOnEscalation(_ => calls++)
            .Build();
        c.Register("a");
        c.Update("a", 0.8);
        Assert.Equal(1, calls);
    }

    public void TestRejectsBadPressure()
    {
        var c = SharedPressureCoordinator.CreateBuilder()
            .WithClock(new DelegateCoordClock(() => 0.0))
            .Build();
        Assert.Throws<CoordinatorException>(() => c.Update("a", 1.5));
        Assert.Throws<CoordinatorException>(() => c.Update("a", -0.1));
    }

    public void TestLuaScriptUnchangedFromSpec()
    {
        Assert.Contains("pressures_key = KEYS[1]", RedisCoordinator.UpdateAndFetchScript);
        Assert.Contains("HGETALL", RedisCoordinator.UpdateAndFetchScript);
        Assert.Contains("EXPIRE", RedisCoordinator.UpdateAndFetchScript);
    }

    public void TestParseHGetAllFlat()
    {
        var reply = new List<string> { "a", "0.3", "b", "0.5" };
        var @out = RedisCoordinator.ParseHGetAllFlat(reply);
        Assert.EqualDouble(0.3, @out["a"]);
        Assert.EqualDouble(0.5, @out["b"]);
    }

    private sealed class MockRedis : IRedisClient
    {
        public Dictionary<string, Dictionary<string, string>> Hashes = new();

        public object? Eval(string script, string[] keys, string[] args)
        {
            string key = keys[0];
            if (!Hashes.TryGetValue(key, out var h))
            {
                h = new Dictionary<string, string>();
                Hashes[key] = h;
            }
            if (script.Contains("HSET") && script.Contains("HGETALL"))
            {
                h[args[0]] = args[1];
                var flat = new List<string>();
                foreach (var kv in h) { flat.Add(kv.Key); flat.Add(kv.Value); }
                return flat;
            }
            if (script.Contains("HDEL"))
            {
                h.Remove(args[0]);
                return 1L;
            }
            return null;
        }

        public void HSet(string key, IReadOnlyList<KeyValuePair<string, string>> pairs)
        {
            if (!Hashes.TryGetValue(key, out var h))
            {
                h = new Dictionary<string, string>();
                Hashes[key] = h;
            }
            foreach (var p in pairs) h[p.Key] = p.Value;
        }

        public IReadOnlyList<string> HKeys(string key)
        {
            return Hashes.TryGetValue(key, out var h) ? new List<string>(h.Keys) : new List<string>();
        }
    }

    public void TestRedisCoordinatorWithMock()
    {
        var mock = new MockRedis();
        var c = RedisCoordinator.CreateBuilder()
            .WithRedis(mock)
            .WithCoordinatorId("test")
            .WithEscalationThreshold(0.7)
            .WithReleaseThreshold(0.9)
            .WithPressuresTtlSeconds(300)
            .WithAggregator(new SumAggregator())
            .WithAuditSink(new MemorySink())
            .WithClock(new DelegateCoordClock(() => 0.0))
            .Build();
        c.Register("a");
        c.Register("b");
        c.Update("a", 0.4);
        var snap = c.Update("b", 0.3);
        Assert.EqualDouble(0.7, snap.AggregatePressure);
    }
}

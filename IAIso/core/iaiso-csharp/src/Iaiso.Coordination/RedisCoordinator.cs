using System;
using System.Collections.Generic;
using Iaiso.Audit;
using Iaiso.Policy;

namespace Iaiso.Coordination;

/// <summary>
/// Structural Redis client interface. Implement this around your favorite
/// Redis library (StackExchange.Redis, ServiceStack.Redis, etc.) to plug
/// it into <see cref="RedisCoordinator"/>.
/// </summary>
public interface IRedisClient
{
    /// <summary>Run a Lua script. Returns a parsed Redis reply.</summary>
    object? Eval(string script, string[] keys, string[] args);

    /// <summary>HSET key field value [field value ...]</summary>
    void HSet(string key, IReadOnlyList<KeyValuePair<string, string>> fieldValuePairs);

    /// <summary>HKEYS key</summary>
    IReadOnlyList<string> HKeys(string key);
}

/// <summary>
/// Redis-backed coordinator. Interoperable with the Python, Node, Go,
/// Rust, and Java references via the shared keyspace and the verbatim
/// Lua script in <see cref="UpdateAndFetchScript"/>.
/// </summary>
public sealed class RedisCoordinator
{
    /// <summary>
    /// The normative Lua script — verbatim from
    /// <c>spec/coordinator/README.md §1.2</c>. Bytes are identical
    /// across all reference SDKs to ensure cross-language fleet
    /// coordination.
    /// </summary>
    public const string UpdateAndFetchScript =
        "\nlocal pressures_key = KEYS[1]\n"
        + "local exec_id       = ARGV[1]\n"
        + "local new_pressure  = ARGV[2]\n"
        + "local ttl_seconds   = tonumber(ARGV[3])\n"
        + "\n"
        + "redis.call('HSET', pressures_key, exec_id, new_pressure)\n"
        + "if ttl_seconds > 0 then\n"
        + "  redis.call('EXPIRE', pressures_key, ttl_seconds)\n"
        + "end\n"
        + "\n"
        + "return redis.call('HGETALL', pressures_key)\n";

    private readonly IRedisClient _redis;
    private readonly string _keyPrefix;
    private readonly long _pressuresTtlSeconds;
    private readonly SharedPressureCoordinator _shadow;
    private readonly ISink _auditSink;
    private readonly ICoordClock _clock;

    private RedisCoordinator(Builder b)
    {
        _redis = b.Redis ?? throw new CoordinatorException("redis is required");
        _keyPrefix = b.KeyPrefix;
        _pressuresTtlSeconds = b.PressuresTtlSeconds;
        _auditSink = b.AuditSink ?? NullSink.Instance;
        _clock = b.Clock ?? CoordWallClock.Instance;
        _shadow = new SharedPressureCoordinator(b.CoordinatorId,
            b.EscalationThreshold, b.ReleaseThreshold, b.NotifyCooldownSeconds,
            b.Aggregator, NullSink.Instance, b.OnEscalation, b.OnRelease,
            _clock, false);
        // Emit init with backend=redis using the user's audit sink.
        var data = new SortedDictionary<string, object?>
        {
            ["coordinator_id"] = b.CoordinatorId,
            ["aggregator"] = b.Aggregator.Name,
            ["backend"] = "redis",
        };
        _auditSink.Emit(new Event($"coord:{b.CoordinatorId}",
            "coordinator.init", _clock.Now(), data));
    }

    public static Builder CreateBuilder() => new();

    private string PressuresKey() => $"{_keyPrefix}:{_shadow.CoordinatorId}:pressures";

    public Snapshot Register(string executionId)
    {
        _redis.HSet(PressuresKey(), new[] { new KeyValuePair<string, string>(executionId, "0.0") });
        return _shadow.Register(executionId);
    }

    public Snapshot Unregister(string executionId)
    {
        _redis.Eval("redis.call('HDEL', KEYS[1], ARGV[1]); return 1",
            new[] { PressuresKey() }, new[] { executionId });
        return _shadow.Unregister(executionId);
    }

    public Snapshot Update(string executionId, double pressure)
    {
        if (pressure < 0.0 || pressure > 1.0)
            throw new CoordinatorException($"pressure must be in [0, 1], got {pressure}");
        var result = _redis.Eval(UpdateAndFetchScript,
            new[] { PressuresKey() },
            new[] { executionId,
                pressure.ToString(System.Globalization.CultureInfo.InvariantCulture),
                _pressuresTtlSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture) });
        var updated = ParseHGetAllFlat(result);
        _shadow.SetPressuresFromMap(updated);
        return _shadow.Evaluate();
    }

    public int Reset()
    {
        var keys = _redis.HKeys(PressuresKey());
        if (keys.Count > 0)
        {
            var pairs = new List<KeyValuePair<string, string>>(keys.Count);
            foreach (var k in keys) pairs.Add(new KeyValuePair<string, string>(k, "0.0"));
            _redis.HSet(PressuresKey(), pairs);
        }
        return _shadow.Reset();
    }

    public Snapshot Snapshot() => _shadow.Snapshot();

    /// <summary>
    /// Parse a flat HGETALL Redis reply into a string→double map.
    /// Accepts a list of alternating keys/values, or a pre-parsed dict.
    /// </summary>
    public static IReadOnlyDictionary<string, double> ParseHGetAllFlat(object? reply)
    {
        var result = new SortedDictionary<string, double>();
        if (reply is null) return result;
        if (reply is IReadOnlyDictionary<string, object?> dict)
        {
            foreach (var kv in dict)
            {
                if (TryParseDouble(kv.Value, out var d)) result[kv.Key] = d;
            }
            return result;
        }
        if (reply is System.Collections.IDictionary idict)
        {
            foreach (var key in idict.Keys)
            {
                if (TryParseDouble(idict[key], out var d))
                    result[key.ToString() ?? ""] = d;
            }
            return result;
        }
        if (reply is System.Collections.IEnumerable e)
        {
            object? lastKey = null;
            int idx = 0;
            foreach (var item in e)
            {
                if (idx % 2 == 0) lastKey = item;
                else if (TryParseDouble(item, out var d) && lastKey is not null)
                    result[lastKey.ToString() ?? ""] = d;
                idx++;
            }
        }
        return result;
    }

    private static bool TryParseDouble(object? v, out double d)
    {
        if (v is null) { d = 0; return false; }
        if (v is double dd) { d = dd; return true; }
        if (v is long l) { d = l; return true; }
        if (v is int i) { d = i; return true; }
        return double.TryParse(v.ToString(),
            System.Globalization.NumberStyles.Float,
            System.Globalization.CultureInfo.InvariantCulture, out d);
    }

    public sealed class Builder
    {
        public IRedisClient? Redis { get; set; }
        public string CoordinatorId { get; set; } = "default";
        public double EscalationThreshold { get; set; } = 5.0;
        public double ReleaseThreshold { get; set; } = 8.0;
        public double NotifyCooldownSeconds { get; set; } = 1.0;
        public string KeyPrefix { get; set; } = "iaiso:coord";
        public long PressuresTtlSeconds { get; set; } = 300;
        public IAggregator Aggregator { get; set; } = new SumAggregator();
        public ISink? AuditSink { get; set; }
        public Action<Snapshot>? OnEscalation { get; set; }
        public Action<Snapshot>? OnRelease { get; set; }
        public ICoordClock? Clock { get; set; }

        public Builder WithRedis(IRedisClient v) { Redis = v; return this; }
        public Builder WithCoordinatorId(string v) { CoordinatorId = v; return this; }
        public Builder WithEscalationThreshold(double v) { EscalationThreshold = v; return this; }
        public Builder WithReleaseThreshold(double v) { ReleaseThreshold = v; return this; }
        public Builder WithNotifyCooldownSeconds(double v) { NotifyCooldownSeconds = v; return this; }
        public Builder WithKeyPrefix(string v) { KeyPrefix = v; return this; }
        public Builder WithPressuresTtlSeconds(long v) { PressuresTtlSeconds = v; return this; }
        public Builder WithAggregator(IAggregator v) { Aggregator = v; return this; }
        public Builder WithAuditSink(ISink v) { AuditSink = v; return this; }
        public Builder WithOnEscalation(Action<Snapshot> v) { OnEscalation = v; return this; }
        public Builder WithOnRelease(Action<Snapshot> v) { OnRelease = v; return this; }
        public Builder WithClock(ICoordClock v) { Clock = v; return this; }

        public RedisCoordinator Build() => new(this);
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json.Nodes;
using Iaiso.Audit;
using Iaiso.Core;

namespace Iaiso.Conformance;

internal static class EventsRunner
{
    public static List<VectorResult> Run(string specRoot)
    {
        var path = Path.Combine(specRoot, "events", "vectors.json");
        var doc = JsonNode.Parse(File.ReadAllBytes(path))!.AsObject();
        var vectors = doc["vectors"]!.AsArray();
        var results = new List<VectorResult>(vectors.Count);
        foreach (var v in vectors) results.Add(RunOne(v!.AsObject()));
        return results;
    }

    private static VectorResult RunOne(JsonObject v)
    {
        string name = v["name"]!.GetValue<string>();

        var cb = PressureConfig.CreateBuilder();
        if (v["config"] is JsonObject c)
        {
            ApplyDouble(c, "escalation_threshold", x => cb.EscalationThreshold = x);
            ApplyDouble(c, "release_threshold", x => cb.ReleaseThreshold = x);
            ApplyDouble(c, "dissipation_per_step", x => cb.DissipationPerStep = x);
            ApplyDouble(c, "dissipation_per_second", x => cb.DissipationPerSecond = x);
            ApplyDouble(c, "token_coefficient", x => cb.TokenCoefficient = x);
            ApplyDouble(c, "tool_coefficient", x => cb.ToolCoefficient = x);
            ApplyDouble(c, "depth_coefficient", x => cb.DepthCoefficient = x);
            if (c["post_release_lock"] is JsonValue prl && prl.TryGetValue<bool>(out var b))
                cb.PostReleaseLock = b;
        }
        var cfg = cb.Build();

        double[] clockSeq;
        if (v["clock"] is JsonArray clkArr)
        {
            clockSeq = new double[clkArr.Count];
            for (int i = 0; i < clkArr.Count; i++) clockSeq[i] = clkArr[i]!.GetValue<double>();
        }
        else
        {
            clockSeq = new[] { 0.0 };
        }
        var clock = new ScriptedClock(clockSeq);

        var sink = new MemorySink();
        string execId = v["execution_id"]!.GetValue<string>();
        PressureEngine engine;
        try
        {
            engine = new PressureEngine(cfg, new EngineOptions
            {
                ExecutionId = execId,
                AuditSink = sink,
                Clock = clock,
                TimestampClock = clock,
            });
        }
        catch (Exception e)
        {
            return VectorResult.Fail("events", name, "engine init failed: " + e.Message);
        }

        int? resetAfterStep = v["reset_after_step"] is JsonValue rs
            && rs.TryGetValue<int>(out var rsi) ? rsi : null;

        var steps = v["steps"] as JsonArray ?? new JsonArray();
        for (int i = 0; i < steps.Count; i++)
        {
            var step = steps[i]!.AsObject();
            if (step["reset"] is JsonValue rv && rv.TryGetValue<bool>(out var resetB) && resetB)
            {
                engine.Reset();
            }
            else
            {
                var si = new StepInput();
                if (step["tokens"] is JsonValue tv) si.Tokens = tv.GetValue<long>();
                if (step["tool_calls"] is JsonValue tcv) si.ToolCalls = tcv.GetValue<long>();
                if (step["depth"] is JsonValue dv) si.Depth = dv.GetValue<long>();
                if (step["tag"] is JsonValue tg && tg.TryGetValue<string>(out var tag)) si.Tag = tag;
                engine.Step(si);
            }
            if (resetAfterStep.HasValue && (i + 1) == resetAfterStep.Value)
            {
                engine.Reset();
            }
        }

        var got = sink.Events();
        var expected = v["expected_events"]!.AsArray();
        if (got.Count != expected.Count)
            return VectorResult.Fail("events", name,
                $"event count: got {got.Count}, want {expected.Count}");

        for (int i = 0; i < expected.Count; i++)
        {
            var exp = expected[i]!.AsObject();
            var actual = got[i];
            if (exp["schema_version"] is JsonValue sv && sv.TryGetValue<string>(out var svs)
                && !string.IsNullOrEmpty(svs) && svs != actual.SchemaVersion)
                return VectorResult.Fail("events", name,
                    $"event {i} schema_version: got {actual.SchemaVersion}, want {svs}");
            if (exp["execution_id"] is JsonValue ev && ev.TryGetValue<string>(out var evs)
                && !string.IsNullOrEmpty(evs) && evs != actual.ExecutionId)
                return VectorResult.Fail("events", name,
                    $"event {i} execution_id: got {actual.ExecutionId}, want {evs}");
            string wantKind = exp["kind"]!.GetValue<string>();
            if (wantKind != actual.Kind)
                return VectorResult.Fail("events", name,
                    $"event {i} kind: got {actual.Kind}, want {wantKind}");
            if (exp["data"] is JsonObject expData)
            {
                if (!DataMatches(actual.Data, expData))
                    return VectorResult.Fail("events", name,
                        $"event {i} data mismatch: got {ActualToJson(actual.Data)}, want {expData.ToJsonString()}");
            }
        }
        return VectorResult.Pass("events", name);
    }

    private static string ActualToJson(IReadOnlyDictionary<string, object?> data)
    {
        // For diagnostic output only
        var obj = new JsonObject();
        foreach (var kv in data)
        {
            obj[kv.Key] = kv.Value switch
            {
                null => null,
                string s => JsonValue.Create(s),
                bool b => JsonValue.Create(b),
                long l => JsonValue.Create(l),
                int i => JsonValue.Create(i),
                double d => JsonValue.Create(d),
                _ => JsonValue.Create(kv.Value.ToString()),
            };
        }
        return obj.ToJsonString();
    }

    private static bool DataMatches(IReadOnlyDictionary<string, object?> actual, JsonObject want)
    {
        foreach (var entry in want)
        {
            object? got = actual.TryGetValue(entry.Key, out var v) ? v : null;
            if (!ValueEqual(got, entry.Value)) return false;
        }
        return true;
    }

    private static bool ValueEqual(object? actual, JsonNode? want)
    {
        if (want is null) return actual is null;
        if (actual is null) return false;
        if (want is JsonValue v)
        {
            if (v.TryGetValue<bool>(out var b))
                return actual is bool ab && ab == b;
            if (v.TryGetValue<double>(out var d))
            {
                if (actual is double ad) return Math.Abs(ad - d) <= ConformanceRunner.Tolerance;
                if (actual is long al) return Math.Abs((double)al - d) <= ConformanceRunner.Tolerance;
                if (actual is int ai) return Math.Abs((double)ai - d) <= ConformanceRunner.Tolerance;
                return false;
            }
            if (v.TryGetValue<string>(out var s))
                return actual is string @as && @as == s;
        }
        if (want is JsonArray arr)
        {
            if (actual is not System.Collections.IEnumerable e) return false;
            var aList = new List<object?>();
            foreach (var item in e) aList.Add(item);
            if (aList.Count != arr.Count) return false;
            for (int i = 0; i < arr.Count; i++)
                if (!ValueEqual(aList[i], arr[i])) return false;
            return true;
        }
        if (want is JsonObject obj)
        {
            if (actual is not IReadOnlyDictionary<string, object?> aDict) return false;
            foreach (var kv in obj)
            {
                object? got = aDict.TryGetValue(kv.Key, out var x) ? x : null;
                if (!ValueEqual(got, kv.Value)) return false;
            }
            return true;
        }
        return false;
    }

    private static void ApplyDouble(JsonObject obj, string key, Action<double> setter)
    {
        if (obj[key] is JsonValue v && v.TryGetValue<double>(out var d)) setter(d);
    }
}

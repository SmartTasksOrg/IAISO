using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json.Nodes;
using Iaiso.Audit;
using Iaiso.Core;

namespace Iaiso.Conformance;

internal static class PressureRunner
{
    public static List<VectorResult> Run(string specRoot)
    {
        var path = Path.Combine(specRoot, "pressure", "vectors.json");
        var doc = JsonNode.Parse(File.ReadAllBytes(path))!.AsObject();
        var vectors = doc["vectors"]!.AsArray();
        var results = new List<VectorResult>(vectors.Count);
        foreach (var v in vectors)
        {
            results.Add(RunOne(v!.AsObject()));
        }
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

        string? expectErr = v["expect_config_error"]?.GetValue<string>();
        PressureEngine engine;
        try
        {
            engine = new PressureEngine(cfg, new EngineOptions
            {
                ExecutionId = "vec-" + name,
                AuditSink = NullSink.Instance,
                Clock = clock,
                TimestampClock = clock,
            });
        }
        catch (ConfigException e)
        {
            if (expectErr is null)
                return VectorResult.Fail("pressure", name,
                    "engine construction failed: " + e.Message);
            if (!e.Message.Contains(expectErr))
                return VectorResult.Fail("pressure", name,
                    $"expected error containing '{expectErr}', got: {e.Message}");
            return VectorResult.Pass("pressure", name);
        }
        if (expectErr is not null)
            return VectorResult.Fail("pressure", name,
                $"expected config error containing '{expectErr}', got Ok");

        if (v["expected_initial"] is JsonObject init)
        {
            var snap = engine.Snapshot();
            if (Math.Abs(snap.Pressure - init["pressure"]!.GetValue<double>()) > ConformanceRunner.Tolerance)
                return VectorResult.Fail("pressure", name,
                    $"initial pressure: got {snap.Pressure}, want {init["pressure"]!.GetValue<double>()}");
            if (snap.Step != init["step"]!.GetValue<long>())
                return VectorResult.Fail("pressure", name,
                    $"initial step: got {snap.Step}, want {init["step"]!.GetValue<long>()}");
            if (snap.Lifecycle.Wire() != init["lifecycle"]!.GetValue<string>())
                return VectorResult.Fail("pressure", name,
                    $"initial lifecycle: got {snap.Lifecycle.Wire()}, want {init["lifecycle"]!.GetValue<string>()}");
            if (Math.Abs(snap.LastStepAt - init["last_step_at"]!.GetValue<double>()) > ConformanceRunner.Tolerance)
                return VectorResult.Fail("pressure", name,
                    $"initial last_step_at: got {snap.LastStepAt}, want {init["last_step_at"]!.GetValue<double>()}");
        }

        var steps = v["steps"] as JsonArray ?? new JsonArray();
        var expSteps = v["expected_steps"] as JsonArray ?? new JsonArray();
        for (int i = 0; i < steps.Count; i++)
        {
            var step = steps[i]!.AsObject();
            StepOutcome outcome;
            if (step["reset"] is JsonValue rv && rv.TryGetValue<bool>(out var resetB) && resetB)
            {
                engine.Reset();
                outcome = StepOutcome.Ok;
            }
            else
            {
                var si = new StepInput();
                if (step["tokens"] is JsonValue tv) si.Tokens = tv.GetValue<long>();
                if (step["tool_calls"] is JsonValue tcv) si.ToolCalls = tcv.GetValue<long>();
                if (step["depth"] is JsonValue dv) si.Depth = dv.GetValue<long>();
                if (step["tag"] is JsonValue tg && tg.TryGetValue<string>(out var tag)) si.Tag = tag;
                outcome = engine.Step(si);
            }
            if (i >= expSteps.Count)
                return VectorResult.Fail("pressure", name,
                    $"step {i}: no expected entry");
            var exp = expSteps[i]!.AsObject();
            if (outcome.Wire() != exp["outcome"]!.GetValue<string>())
                return VectorResult.Fail("pressure", name,
                    $"step {i}: outcome got {outcome.Wire()}, want {exp["outcome"]!.GetValue<string>()}");
            var snap = engine.Snapshot();
            if (Math.Abs(snap.Pressure - exp["pressure"]!.GetValue<double>()) > ConformanceRunner.Tolerance)
                return VectorResult.Fail("pressure", name,
                    $"step {i}: pressure got {snap.Pressure}, want {exp["pressure"]!.GetValue<double>()}");
            if (snap.Step != exp["step"]!.GetValue<long>())
                return VectorResult.Fail("pressure", name,
                    $"step {i}: step got {snap.Step}, want {exp["step"]!.GetValue<long>()}");
            if (snap.Lifecycle.Wire() != exp["lifecycle"]!.GetValue<string>())
                return VectorResult.Fail("pressure", name,
                    $"step {i}: lifecycle got {snap.Lifecycle.Wire()}, want {exp["lifecycle"]!.GetValue<string>()}");
        }
        return VectorResult.Pass("pressure", name);
    }

    private static void ApplyDouble(JsonObject obj, string key, Action<double> setter)
    {
        if (obj[key] is JsonValue v && v.TryGetValue<double>(out var d)) setter(d);
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json.Nodes;
using Iaiso.Policy;

namespace Iaiso.Conformance;

internal static class PolicyRunner
{
    public static List<VectorResult> Run(string specRoot)
    {
        var path = Path.Combine(specRoot, "policy", "vectors.json");
        var doc = JsonNode.Parse(File.ReadAllBytes(path))!.AsObject();
        var results = new List<VectorResult>();
        if (doc["valid"] is JsonArray valid)
            foreach (var v in valid) results.Add(RunValid(v!.AsObject()));
        if (doc["invalid"] is JsonArray invalid)
            foreach (var v in invalid) results.Add(RunInvalid(v!.AsObject()));
        return results;
    }

    private static VectorResult RunValid(JsonObject v)
    {
        string name = "valid/" + v["name"]!.GetValue<string>();
        try
        {
            var p = PolicyLoader.Build(v["document"]);
            if (v["expected_pressure"] is JsonObject ep)
            {
                string? err = CheckPressure(p, ep);
                if (err is not null) return VectorResult.Fail("policy", name, err);
            }
            if (v["expected_consent"] is JsonObject ec)
            {
                string? err = CheckConsent(p, ec);
                if (err is not null) return VectorResult.Fail("policy", name, err);
            }
            if (v["expected_metadata"] is JsonObject em)
            {
                if (em.Count != p.Metadata.Count)
                    return VectorResult.Fail("policy", name,
                        $"metadata size: got {p.Metadata.Count}, want {em.Count}");
            }
            return VectorResult.Pass("policy", name);
        }
        catch (Exception e)
        {
            return VectorResult.Fail("policy", name, "build failed: " + e.Message);
        }
    }

    private static string? CheckPressure(Iaiso.Policy.Policy p, JsonObject ep)
    {
        string[] labels = {
            "token_coefficient", "tool_coefficient", "depth_coefficient",
            "dissipation_per_step", "dissipation_per_second",
            "escalation_threshold", "release_threshold"
        };
        double[] gots = {
            p.Pressure.TokenCoefficient, p.Pressure.ToolCoefficient,
            p.Pressure.DepthCoefficient, p.Pressure.DissipationPerStep,
            p.Pressure.DissipationPerSecond, p.Pressure.EscalationThreshold,
            p.Pressure.ReleaseThreshold,
        };
        for (int i = 0; i < labels.Length; i++)
        {
            if (ep[labels[i]] is JsonValue v && v.TryGetValue<double>(out var d))
            {
                if (Math.Abs(gots[i] - d) > ConformanceRunner.Tolerance)
                    return $"{labels[i]}: got {gots[i]}, want {d}";
            }
        }
        if (ep["post_release_lock"] is JsonValue prl && prl.TryGetValue<bool>(out var b))
        {
            if (b != p.Pressure.PostReleaseLock) return "post_release_lock mismatch";
        }
        return null;
    }

    private static string? CheckConsent(Iaiso.Policy.Policy p, JsonObject ec)
    {
        if (ec["issuer"] is not null)
        {
            string? want = ec["issuer"] is JsonValue iv && iv.TryGetValue<string>(out var s)
                ? s : null;
            if (want is null ? p.Consent.Issuer is not null : want != p.Consent.Issuer)
                return $"consent.issuer: got {p.Consent.Issuer}, want {want}";
        }
        if (ec["default_ttl_seconds"] is JsonValue tv && tv.TryGetValue<double>(out var t))
        {
            if (Math.Abs(p.Consent.DefaultTtlSeconds - t) > ConformanceRunner.Tolerance)
                return $"default_ttl_seconds: got {p.Consent.DefaultTtlSeconds}, want {t}";
        }
        if (ec["required_scopes"] is JsonArray rs && rs.Count != p.Consent.RequiredScopes.Count)
            return "required_scopes length mismatch";
        if (ec["allowed_algorithms"] is JsonArray aa && aa.Count != p.Consent.AllowedAlgorithms.Count)
            return "allowed_algorithms length mismatch";
        return null;
    }

    private static VectorResult RunInvalid(JsonObject v)
    {
        string name = "invalid/" + v["name"]!.GetValue<string>();
        string expectPath = v["expect_error_path"]!.GetValue<string>();
        try
        {
            PolicyLoader.Build(v["document"]);
            return VectorResult.Fail("policy", name,
                $"expected error containing '{expectPath}', got Ok");
        }
        catch (PolicyException e)
        {
            return e.Message.Contains(expectPath)
                ? VectorResult.Pass("policy", name)
                : VectorResult.Fail("policy", name,
                    $"expected error containing '{expectPath}', got: {e.Message}");
        }
    }
}

using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Iaiso.Core;

namespace Iaiso.Policy;

/// <summary>
/// IAIso policy loader. JSON only — System.Text.Json provides JSON
/// support out of the box, and the C# port deliberately avoids extra
/// dependencies. Convert YAML policies to JSON outside this SDK if
/// needed.
/// </summary>
public static class PolicyLoader
{
    private static readonly Regex ScopePattern =
        new(@"^[a-z0-9_-]+(\.[a-z0-9_-]+)*$", RegexOptions.Compiled);

    /// <summary>Validate a parsed JSON document against <c>spec/policy/README.md</c>.</summary>
    public static void Validate(JsonNode? doc)
    {
        if (doc is not JsonObject root)
        {
            throw new PolicyException("$: policy document must be a mapping");
        }

        if (!root.ContainsKey("version"))
        {
            throw new PolicyException("$: required property 'version' missing");
        }
        if (root["version"] is not JsonValue vNode || !vNode.TryGetValue<string>(out var vs) || vs != "1")
        {
            var got = root["version"]?.ToJsonString() ?? "null";
            throw new PolicyException($"$.version: must be exactly \"1\", got {got}");
        }

        if (root["pressure"] is JsonNode pressureNode)
        {
            if (pressureNode is not JsonObject pObj)
                throw new PolicyException("$.pressure: must be a mapping");

            string[] nonNeg = {
                "token_coefficient", "tool_coefficient", "depth_coefficient",
                "dissipation_per_step", "dissipation_per_second"
            };
            foreach (var f in nonNeg)
            {
                if (pObj[f] is JsonNode fn)
                {
                    double? n = TryNumber(fn);
                    if (n is null) throw new PolicyException($"$.pressure.{f}: expected number");
                    if (n < 0) throw new PolicyException(
                        $"$.pressure.{f}: must be non-negative (got {n})");
                }
            }
            string[] thresholds = { "escalation_threshold", "release_threshold" };
            foreach (var f in thresholds)
            {
                if (pObj[f] is JsonNode fn)
                {
                    double? n = TryNumber(fn);
                    if (n is null) throw new PolicyException($"$.pressure.{f}: expected number");
                    if (n < 0 || n > 1) throw new PolicyException(
                        $"$.pressure.{f}: must be in [0, 1] (got {n})");
                }
            }
            if (pObj["post_release_lock"] is JsonNode prl
                && !TryBool(prl, out _))
            {
                throw new PolicyException("$.pressure.post_release_lock: expected boolean");
            }
            // Cross-field
            double? esc = pObj["escalation_threshold"] is JsonNode escn
                ? TryNumber(escn) : null;
            double? rel = pObj["release_threshold"] is JsonNode reln
                ? TryNumber(reln) : null;
            if (esc.HasValue && rel.HasValue && rel <= esc)
                throw new PolicyException(
                    $"$.pressure.release_threshold: must exceed escalation_threshold ({rel} <= {esc})");
        }

        if (root["coordinator"] is JsonNode coordNode)
        {
            if (coordNode is not JsonObject cObj)
                throw new PolicyException("$.coordinator: must be a mapping");
            if (cObj["aggregator"] is JsonNode an)
            {
                string? name = an is JsonValue av && av.TryGetValue<string>(out var s) ? s : null;
                if (name is null || (name != "sum" && name != "mean"
                                     && name != "max" && name != "weighted_sum"))
                {
                    throw new PolicyException(
                        $"$.coordinator.aggregator: must be one of sum|mean|max|weighted_sum (got {an.ToJsonString()})");
                }
            }
            double? cesc = cObj["escalation_threshold"] is JsonNode escn
                ? TryNumber(escn) : null;
            double? crel = cObj["release_threshold"] is JsonNode reln
                ? TryNumber(reln) : null;
            if (cesc.HasValue && crel.HasValue && crel <= cesc)
                throw new PolicyException(
                    $"$.coordinator.release_threshold: must exceed escalation_threshold ({crel} <= {cesc})");
        }

        if (root["consent"] is JsonNode consentNode)
        {
            if (consentNode is not JsonObject cObj)
                throw new PolicyException("$.consent: must be a mapping");
            if (cObj["required_scopes"] is JsonNode rsn)
            {
                if (rsn is not JsonArray arr)
                    throw new PolicyException("$.consent.required_scopes: expected list");
                for (int i = 0; i < arr.Count; i++)
                {
                    string s = arr[i]?.GetValue<string>() ?? "";
                    if (!ScopePattern.IsMatch(s))
                        throw new PolicyException(
                            $"$.consent.required_scopes[{i}]: {s} is not a valid scope");
                }
            }
        }
    }

    /// <summary>Build a <see cref="Policy"/> from a parsed JSON document.</summary>
    public static Policy Build(JsonNode? doc)
    {
        Validate(doc);
        var root = (JsonObject)doc!;

        var pcb = PressureConfig.CreateBuilder();
        if (root["pressure"] is JsonObject p)
        {
            ApplyDouble(p, "escalation_threshold", v => pcb.EscalationThreshold = v);
            ApplyDouble(p, "release_threshold", v => pcb.ReleaseThreshold = v);
            ApplyDouble(p, "dissipation_per_step", v => pcb.DissipationPerStep = v);
            ApplyDouble(p, "dissipation_per_second", v => pcb.DissipationPerSecond = v);
            ApplyDouble(p, "token_coefficient", v => pcb.TokenCoefficient = v);
            ApplyDouble(p, "tool_coefficient", v => pcb.ToolCoefficient = v);
            ApplyDouble(p, "depth_coefficient", v => pcb.DepthCoefficient = v);
            if (p["post_release_lock"] is JsonNode prl && TryBool(prl, out var b))
                pcb.PostReleaseLock = b;
        }
        var pressure = pcb.Build();
        try { pressure.Validate(); }
        catch (ConfigException e) { throw new PolicyException("$.pressure: " + e.Message, e); }

        var coord = CoordinatorConfig.Defaults();
        IAggregator aggregator = new SumAggregator();
        if (root["coordinator"] is JsonObject c)
        {
            double escThr = c["escalation_threshold"] is JsonNode escn && TryNumber(escn) is double esc
                ? esc : coord.EscalationThreshold;
            double relThr = c["release_threshold"] is JsonNode reln && TryNumber(reln) is double rel
                ? rel : coord.ReleaseThreshold;
            double cooldown = c["notify_cooldown_seconds"] is JsonNode cdn && TryNumber(cdn) is double cd
                ? cd : coord.NotifyCooldownSeconds;
            coord = new CoordinatorConfig(escThr, relThr, cooldown);
            aggregator = BuildAggregator(c);
        }

        var consent = ConsentPolicy.Defaults();
        if (root["consent"] is JsonObject cc)
        {
            string? issuer = cc["issuer"]?.GetValue<string>();
            double ttl = cc["default_ttl_seconds"] is JsonNode tn && TryNumber(tn) is double t
                ? t : consent.DefaultTtlSeconds;
            var required = consent.RequiredScopes;
            if (cc["required_scopes"] is JsonArray reqArr)
            {
                var tmp = new List<string>();
                foreach (var n in reqArr) if (n is not null) tmp.Add(n.GetValue<string>());
                required = tmp;
            }
            var algos = consent.AllowedAlgorithms;
            if (cc["allowed_algorithms"] is JsonArray algArr)
            {
                var tmp = new List<string>();
                foreach (var n in algArr) if (n is not null) tmp.Add(n.GetValue<string>());
                algos = tmp;
            }
            consent = new ConsentPolicy(issuer, ttl, required, algos);
        }

        var metadata = root["metadata"] is JsonObject mo
            ? (JsonObject)JsonNode.Parse(mo.ToJsonString())!
            : new JsonObject();

        return new Policy("1", pressure, coord, consent, aggregator, metadata);
    }

    /// <summary>Parse JSON-encoded policy bytes.</summary>
    public static Policy ParseJson(byte[] data)
    {
        try
        {
            var doc = JsonNode.Parse(data);
            return Build(doc);
        }
        catch (PolicyException) { throw; }
        catch (Exception e)
        {
            throw new PolicyException("policy JSON parse failed: " + e.Message, e);
        }
    }

    /// <summary>Load a policy from a file (.json only).</summary>
    public static Policy Load(string path)
    {
        try
        {
            byte[] data = File.ReadAllBytes(path);
            string ext = Path.GetExtension(path).ToLowerInvariant();
            if (ext != ".json")
            {
                throw new PolicyException(
                    $"unsupported policy file extension: {path} (only .json is supported in the C# SDK)");
            }
            return ParseJson(data);
        }
        catch (PolicyException) { throw; }
        catch (IOException e)
        {
            throw new PolicyException($"failed to read {path}: {e.Message}", e);
        }
    }

    private static IAggregator BuildAggregator(JsonObject coord)
    {
        string name = coord["aggregator"]?.GetValue<string>() ?? "sum";
        return name switch
        {
            "mean" => new MeanAggregator(),
            "max" => new MaxAggregator(),
            "weighted_sum" => BuildWeightedSum(coord),
            _ => new SumAggregator(),
        };
    }

    private static WeightedSumAggregator BuildWeightedSum(JsonObject coord)
    {
        var weights = new Dictionary<string, double>();
        if (coord["weights"] is JsonObject w)
        {
            foreach (var kv in w)
            {
                if (kv.Value is not null && TryNumber(kv.Value) is double d)
                {
                    weights[kv.Key] = d;
                }
            }
        }
        double dw = coord["default_weight"] is JsonNode dwn && TryNumber(dwn) is double dwval
            ? dwval : 1.0;
        return new WeightedSumAggregator(weights, dw);
    }

    /// <summary>
    /// Strict number test: rejects strings that happen to parse as numbers.
    /// Required by the wrong_type_for_number_field conformance vector.
    /// </summary>
    private static double? TryNumber(JsonNode? node)
    {
        if (node is not JsonValue v) return null;
        // System.Text.Json requires us to inspect the underlying element kind
        if (v.TryGetValue<double>(out var d)) return d;
        if (v.TryGetValue<long>(out var l)) return l;
        if (v.TryGetValue<int>(out var i)) return i;
        return null;
    }

    private static bool TryBool(JsonNode? node, out bool result)
    {
        if (node is JsonValue v && v.TryGetValue<bool>(out var b))
        {
            result = b;
            return true;
        }
        result = false;
        return false;
    }

    private static void ApplyDouble(JsonObject obj, string key, Action<double> setter)
    {
        if (obj[key] is JsonNode node && TryNumber(node) is double d) setter(d);
    }
}

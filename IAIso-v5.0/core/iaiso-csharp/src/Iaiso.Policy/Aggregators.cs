using System;
using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Core;

namespace Iaiso.Policy;

/// <summary>Wraps a policy validation failure with a JSON-Pointer-like path.</summary>
public class PolicyException : Exception
{
    public PolicyException(string message) : base(message) {}
    public PolicyException(string message, Exception inner) : base(message, inner) {}
}

/// <summary>A coordinator aggregation strategy.</summary>
public interface IAggregator
{
    /// <summary>Wire-format aggregator name.</summary>
    string Name { get; }
    /// <summary>Compute the aggregate from per-execution pressures.</summary>
    double Aggregate(IReadOnlyDictionary<string, double> pressures);
}

public sealed class SumAggregator : IAggregator
{
    public string Name => "sum";
    public double Aggregate(IReadOnlyDictionary<string, double> p)
    {
        double total = 0;
        foreach (var v in p.Values) total += v;
        return total;
    }
}

public sealed class MeanAggregator : IAggregator
{
    public string Name => "mean";
    public double Aggregate(IReadOnlyDictionary<string, double> p)
    {
        if (p.Count == 0) return 0;
        double total = 0;
        foreach (var v in p.Values) total += v;
        return total / p.Count;
    }
}

public sealed class MaxAggregator : IAggregator
{
    public string Name => "max";
    public double Aggregate(IReadOnlyDictionary<string, double> p)
    {
        double max = 0;
        foreach (var v in p.Values) if (v > max) max = v;
        return max;
    }
}

public sealed class WeightedSumAggregator : IAggregator
{
    public IReadOnlyDictionary<string, double> Weights { get; }
    public double DefaultWeight { get; }

    public WeightedSumAggregator(IReadOnlyDictionary<string, double> weights, double defaultWeight)
    {
        Weights = new Dictionary<string, double>(weights);
        DefaultWeight = defaultWeight;
    }

    public string Name => "weighted_sum";
    public double Aggregate(IReadOnlyDictionary<string, double> p)
    {
        double total = 0;
        foreach (var kv in p)
        {
            double w = Weights.TryGetValue(kv.Key, out var found) ? found : DefaultWeight;
            total += w * kv.Value;
        }
        return total;
    }
}

/// <summary>Coordinator-section configuration from a parsed policy.</summary>
public sealed class CoordinatorConfig
{
    public double EscalationThreshold { get; }
    public double ReleaseThreshold { get; }
    public double NotifyCooldownSeconds { get; }

    public CoordinatorConfig(double escalationThreshold, double releaseThreshold,
                             double notifyCooldownSeconds)
    {
        EscalationThreshold = escalationThreshold;
        ReleaseThreshold = releaseThreshold;
        NotifyCooldownSeconds = notifyCooldownSeconds;
    }

    public static CoordinatorConfig Defaults() => new(5.0, 8.0, 1.0);
}

/// <summary>Consent-section configuration from a parsed policy.</summary>
public sealed class ConsentPolicy
{
    public string? Issuer { get; }
    public double DefaultTtlSeconds { get; }
    public IReadOnlyList<string> RequiredScopes { get; }
    public IReadOnlyList<string> AllowedAlgorithms { get; }

    public ConsentPolicy(string? issuer, double defaultTtlSeconds,
                         IReadOnlyList<string> requiredScopes,
                         IReadOnlyList<string> allowedAlgorithms)
    {
        Issuer = issuer;
        DefaultTtlSeconds = defaultTtlSeconds;
        RequiredScopes = requiredScopes;
        AllowedAlgorithms = allowedAlgorithms;
    }

    public static ConsentPolicy Defaults() => new(
        null, 3600.0,
        new List<string>(),
        new List<string> { "HS256", "RS256" });
}

/// <summary>Assembled, validated policy document.</summary>
public sealed class Policy
{
    public string Version { get; }
    public PressureConfig Pressure { get; }
    public CoordinatorConfig Coordinator { get; }
    public ConsentPolicy Consent { get; }
    public IAggregator Aggregator { get; }
    public JsonObject Metadata { get; }

    public Policy(string version, PressureConfig pressure, CoordinatorConfig coordinator,
                  ConsentPolicy consent, IAggregator aggregator, JsonObject? metadata)
    {
        Version = version;
        Pressure = pressure;
        Coordinator = coordinator;
        Consent = consent;
        Aggregator = aggregator;
        Metadata = metadata ?? new JsonObject();
    }
}

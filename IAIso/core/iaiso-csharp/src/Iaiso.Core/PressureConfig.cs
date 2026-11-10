using System;

namespace Iaiso.Core;

/// <summary>Thrown when a <see cref="PressureConfig"/> fails validation.</summary>
public class ConfigException : Exception
{
    public ConfigException(string message) : base(message) {}
}

/// <summary>
/// Pressure engine configuration. See <c>spec/pressure/README.md §2</c>
/// for normative ranges.
/// </summary>
public sealed class PressureConfig
{
    public double EscalationThreshold { get; }
    public double ReleaseThreshold { get; }
    public double DissipationPerStep { get; }
    public double DissipationPerSecond { get; }
    public double TokenCoefficient { get; }
    public double ToolCoefficient { get; }
    public double DepthCoefficient { get; }
    public bool PostReleaseLock { get; }

    private PressureConfig(Builder b)
    {
        EscalationThreshold = b.EscalationThreshold;
        ReleaseThreshold = b.ReleaseThreshold;
        DissipationPerStep = b.DissipationPerStep;
        DissipationPerSecond = b.DissipationPerSecond;
        TokenCoefficient = b.TokenCoefficient;
        ToolCoefficient = b.ToolCoefficient;
        DepthCoefficient = b.DepthCoefficient;
        PostReleaseLock = b.PostReleaseLock;
    }

    public static PressureConfig Defaults() => CreateBuilder().Build();
    public static Builder CreateBuilder() => new();

    public Builder ToBuilder() => new()
    {
        EscalationThreshold = EscalationThreshold,
        ReleaseThreshold = ReleaseThreshold,
        DissipationPerStep = DissipationPerStep,
        DissipationPerSecond = DissipationPerSecond,
        TokenCoefficient = TokenCoefficient,
        ToolCoefficient = ToolCoefficient,
        DepthCoefficient = DepthCoefficient,
        PostReleaseLock = PostReleaseLock,
    };

    public void Validate()
    {
        if (EscalationThreshold < 0.0 || EscalationThreshold > 1.0)
            throw new ConfigException(
                $"escalation_threshold must be in [0, 1], got {EscalationThreshold}");
        if (ReleaseThreshold < 0.0 || ReleaseThreshold > 1.0)
            throw new ConfigException(
                $"release_threshold must be in [0, 1], got {ReleaseThreshold}");
        if (ReleaseThreshold <= EscalationThreshold)
            throw new ConfigException(
                $"release_threshold must exceed escalation_threshold ({ReleaseThreshold} <= {EscalationThreshold})");
        if (TokenCoefficient < 0.0)
            throw new ConfigException(
                $"token_coefficient must be non-negative, got {TokenCoefficient}");
        if (ToolCoefficient < 0.0)
            throw new ConfigException(
                $"tool_coefficient must be non-negative, got {ToolCoefficient}");
        if (DepthCoefficient < 0.0)
            throw new ConfigException(
                $"depth_coefficient must be non-negative, got {DepthCoefficient}");
        if (DissipationPerStep < 0.0)
            throw new ConfigException(
                $"dissipation_per_step must be non-negative, got {DissipationPerStep}");
        if (DissipationPerSecond < 0.0)
            throw new ConfigException(
                $"dissipation_per_second must be non-negative, got {DissipationPerSecond}");
    }

    public sealed class Builder
    {
        public double EscalationThreshold { get; set; } = 0.85;
        public double ReleaseThreshold { get; set; } = 0.95;
        public double DissipationPerStep { get; set; } = 0.02;
        public double DissipationPerSecond { get; set; } = 0.0;
        public double TokenCoefficient { get; set; } = 0.015;
        public double ToolCoefficient { get; set; } = 0.08;
        public double DepthCoefficient { get; set; } = 0.05;
        public bool PostReleaseLock { get; set; } = true;

        public Builder WithEscalationThreshold(double v) { EscalationThreshold = v; return this; }
        public Builder WithReleaseThreshold(double v) { ReleaseThreshold = v; return this; }
        public Builder WithDissipationPerStep(double v) { DissipationPerStep = v; return this; }
        public Builder WithDissipationPerSecond(double v) { DissipationPerSecond = v; return this; }
        public Builder WithTokenCoefficient(double v) { TokenCoefficient = v; return this; }
        public Builder WithToolCoefficient(double v) { ToolCoefficient = v; return this; }
        public Builder WithDepthCoefficient(double v) { DepthCoefficient = v; return this; }
        public Builder WithPostReleaseLock(bool v) { PostReleaseLock = v; return this; }

        public PressureConfig Build() => new(this);
    }
}

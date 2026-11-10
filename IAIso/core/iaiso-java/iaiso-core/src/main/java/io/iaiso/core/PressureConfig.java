package io.iaiso.core;

import java.util.Objects;

/**
 * Pressure engine configuration. See {@code spec/pressure/README.md §2}
 * for normative ranges.
 *
 * <p>The recommended pattern is to start from {@link #defaults()} and
 * use the {@linkplain Builder builder} to override fields:
 *
 * <pre>{@code
 * PressureConfig cfg = PressureConfig.builder()
 *     .escalationThreshold(0.7)
 *     .postReleaseLock(false)
 *     .build();
 * }</pre>
 */
public final class PressureConfig {
    private final double escalationThreshold;
    private final double releaseThreshold;
    private final double dissipationPerStep;
    private final double dissipationPerSecond;
    private final double tokenCoefficient;
    private final double toolCoefficient;
    private final double depthCoefficient;
    private final boolean postReleaseLock;

    private PressureConfig(Builder b) {
        this.escalationThreshold = b.escalationThreshold;
        this.releaseThreshold = b.releaseThreshold;
        this.dissipationPerStep = b.dissipationPerStep;
        this.dissipationPerSecond = b.dissipationPerSecond;
        this.tokenCoefficient = b.tokenCoefficient;
        this.toolCoefficient = b.toolCoefficient;
        this.depthCoefficient = b.depthCoefficient;
        this.postReleaseLock = b.postReleaseLock;
    }

    public double getEscalationThreshold() { return escalationThreshold; }
    public double getReleaseThreshold() { return releaseThreshold; }
    public double getDissipationPerStep() { return dissipationPerStep; }
    public double getDissipationPerSecond() { return dissipationPerSecond; }
    public double getTokenCoefficient() { return tokenCoefficient; }
    public double getToolCoefficient() { return toolCoefficient; }
    public double getDepthCoefficient() { return depthCoefficient; }
    public boolean isPostReleaseLock() { return postReleaseLock; }

    /** A {@link PressureConfig} populated with the spec-default values. */
    public static PressureConfig defaults() {
        return builder().build();
    }

    /** Validate this config. Throws {@link ConfigException} on failure. */
    public void validate() {
        if (escalationThreshold < 0.0 || escalationThreshold > 1.0) {
            throw new ConfigException(
                "escalation_threshold must be in [0, 1], got " + escalationThreshold);
        }
        if (releaseThreshold < 0.0 || releaseThreshold > 1.0) {
            throw new ConfigException(
                "release_threshold must be in [0, 1], got " + releaseThreshold);
        }
        if (releaseThreshold <= escalationThreshold) {
            throw new ConfigException(
                "release_threshold must exceed escalation_threshold (" +
                releaseThreshold + " <= " + escalationThreshold + ")");
        }
        if (tokenCoefficient < 0.0) {
            throw new ConfigException(
                "token_coefficient must be non-negative, got " + tokenCoefficient);
        }
        if (toolCoefficient < 0.0) {
            throw new ConfigException(
                "tool_coefficient must be non-negative, got " + toolCoefficient);
        }
        if (depthCoefficient < 0.0) {
            throw new ConfigException(
                "depth_coefficient must be non-negative, got " + depthCoefficient);
        }
        if (dissipationPerStep < 0.0) {
            throw new ConfigException(
                "dissipation_per_step must be non-negative, got " + dissipationPerStep);
        }
        if (dissipationPerSecond < 0.0) {
            throw new ConfigException(
                "dissipation_per_second must be non-negative, got " + dissipationPerSecond);
        }
    }

    public Builder toBuilder() {
        return new Builder()
            .escalationThreshold(escalationThreshold)
            .releaseThreshold(releaseThreshold)
            .dissipationPerStep(dissipationPerStep)
            .dissipationPerSecond(dissipationPerSecond)
            .tokenCoefficient(tokenCoefficient)
            .toolCoefficient(toolCoefficient)
            .depthCoefficient(depthCoefficient)
            .postReleaseLock(postReleaseLock);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private double escalationThreshold = 0.85;
        private double releaseThreshold = 0.95;
        private double dissipationPerStep = 0.02;
        private double dissipationPerSecond = 0.0;
        private double tokenCoefficient = 0.015;
        private double toolCoefficient = 0.08;
        private double depthCoefficient = 0.05;
        private boolean postReleaseLock = true;

        public Builder escalationThreshold(double v) { this.escalationThreshold = v; return this; }
        public Builder releaseThreshold(double v) { this.releaseThreshold = v; return this; }
        public Builder dissipationPerStep(double v) { this.dissipationPerStep = v; return this; }
        public Builder dissipationPerSecond(double v) { this.dissipationPerSecond = v; return this; }
        public Builder tokenCoefficient(double v) { this.tokenCoefficient = v; return this; }
        public Builder toolCoefficient(double v) { this.toolCoefficient = v; return this; }
        public Builder depthCoefficient(double v) { this.depthCoefficient = v; return this; }
        public Builder postReleaseLock(boolean v) { this.postReleaseLock = v; return this; }

        public PressureConfig build() {
            return new PressureConfig(this);
        }
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof PressureConfig)) return false;
        PressureConfig other = (PressureConfig) o;
        return Double.compare(other.escalationThreshold, escalationThreshold) == 0
            && Double.compare(other.releaseThreshold, releaseThreshold) == 0
            && Double.compare(other.dissipationPerStep, dissipationPerStep) == 0
            && Double.compare(other.dissipationPerSecond, dissipationPerSecond) == 0
            && Double.compare(other.tokenCoefficient, tokenCoefficient) == 0
            && Double.compare(other.toolCoefficient, toolCoefficient) == 0
            && Double.compare(other.depthCoefficient, depthCoefficient) == 0
            && postReleaseLock == other.postReleaseLock;
    }

    @Override
    public int hashCode() {
        return Objects.hash(escalationThreshold, releaseThreshold, dissipationPerStep,
            dissipationPerSecond, tokenCoefficient, toolCoefficient, depthCoefficient,
            postReleaseLock);
    }
}

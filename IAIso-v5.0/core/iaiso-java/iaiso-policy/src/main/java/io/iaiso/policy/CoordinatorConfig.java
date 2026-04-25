package io.iaiso.policy;

/** Coordinator-section configuration from a parsed policy. */
public final class CoordinatorConfig {
    private final double escalationThreshold;
    private final double releaseThreshold;
    private final double notifyCooldownSeconds;

    public CoordinatorConfig(double escalationThreshold, double releaseThreshold,
                             double notifyCooldownSeconds) {
        this.escalationThreshold = escalationThreshold;
        this.releaseThreshold = releaseThreshold;
        this.notifyCooldownSeconds = notifyCooldownSeconds;
    }

    public static CoordinatorConfig defaults() {
        return new CoordinatorConfig(5.0, 8.0, 1.0);
    }

    public double getEscalationThreshold() { return escalationThreshold; }
    public double getReleaseThreshold() { return releaseThreshold; }
    public double getNotifyCooldownSeconds() { return notifyCooldownSeconds; }
}

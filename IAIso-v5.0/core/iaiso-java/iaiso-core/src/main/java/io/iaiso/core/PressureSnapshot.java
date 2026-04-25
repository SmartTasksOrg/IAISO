package io.iaiso.core;

/** Read-only view of pressure-engine state at a point in time. */
public final class PressureSnapshot {
    private final double pressure;
    private final long step;
    private final Lifecycle lifecycle;
    private final double lastDelta;
    private final double lastStepAt;

    public PressureSnapshot(double pressure, long step, Lifecycle lifecycle,
                            double lastDelta, double lastStepAt) {
        this.pressure = pressure;
        this.step = step;
        this.lifecycle = lifecycle;
        this.lastDelta = lastDelta;
        this.lastStepAt = lastStepAt;
    }

    public double getPressure() { return pressure; }
    public long getStep() { return step; }
    public Lifecycle getLifecycle() { return lifecycle; }
    public double getLastDelta() { return lastDelta; }
    public double getLastStepAt() { return lastStepAt; }
}

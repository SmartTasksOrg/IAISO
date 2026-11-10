package io.iaiso.core;

import io.iaiso.audit.Event;
import io.iaiso.audit.NullSink;
import io.iaiso.audit.Sink;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.locks.ReentrantLock;

/**
 * The IAIso pressure engine. Thread-safe; {@code step()} may be called
 * from multiple threads, though semantically each execution should be
 * driven by a single thread.
 *
 * <p>See {@code spec/pressure/README.md} for normative semantics.
 */
public final class PressureEngine {

    private final PressureConfig cfg;
    private final String executionId;
    private final Sink audit;
    private final Clock clock;
    private final Clock timestampClock;
    private final ReentrantLock lock = new ReentrantLock();

    // mutable state guarded by `lock`
    private double pressure;
    private long step;
    private Lifecycle lifecycle;
    private double lastDelta;
    private double lastStepAt;

    public PressureEngine(PressureConfig cfg, EngineOptions opts) {
        cfg.validate();
        this.cfg = cfg;
        this.executionId = opts.getExecutionId();
        this.audit = opts.getAuditSink() != null ? opts.getAuditSink() : NullSink.INSTANCE;
        this.clock = opts.getClock() != null ? opts.getClock() : Clock.wallclock();
        this.timestampClock = opts.getTimestampClock() != null
            ? opts.getTimestampClock()
            : this.clock;
        this.pressure = 0.0;
        this.step = 0L;
        this.lifecycle = Lifecycle.INIT;
        this.lastDelta = 0.0;
        this.lastStepAt = this.clock.now();

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("pressure", 0.0);
        emit("engine.init", data);
    }

    public PressureConfig getConfig() { return cfg; }
    public String getExecutionId() { return executionId; }

    public double getPressure() {
        lock.lock();
        try { return pressure; } finally { lock.unlock(); }
    }

    public Lifecycle getLifecycle() {
        lock.lock();
        try { return lifecycle; } finally { lock.unlock(); }
    }

    public PressureSnapshot snapshot() {
        lock.lock();
        try {
            return new PressureSnapshot(pressure, step, lifecycle, lastDelta, lastStepAt);
        } finally {
            lock.unlock();
        }
    }

    /** Account for a unit of work; advance the engine. */
    public StepOutcome step(StepInput work) {
        // Fast path: locked
        lock.lock();
        try {
            if (lifecycle == Lifecycle.LOCKED) {
                Map<String, Object> data = new LinkedHashMap<>();
                data.put("reason", "locked");
                data.put("requested_tokens", work.getTokens());
                data.put("requested_tools", work.getToolCalls());
                emit("engine.step.rejected", data);
                return StepOutcome.LOCKED;
            }

            double now = clock.now();
            double elapsed = Math.max(0.0, now - lastStepAt);

            double delta = (work.getTokens() / 1000.0) * cfg.getTokenCoefficient()
                + work.getToolCalls() * cfg.getToolCoefficient()
                + work.getDepth() * cfg.getDepthCoefficient();
            double decay = cfg.getDissipationPerStep()
                + elapsed * cfg.getDissipationPerSecond();

            double newPressure = clamp01(pressure + delta - decay);
            this.pressure = newPressure;
            this.step += 1;
            this.lastDelta = delta - decay;
            this.lastStepAt = now;
            this.lifecycle = Lifecycle.RUNNING;

            Map<String, Object> stepData = new LinkedHashMap<>();
            stepData.put("step", step);
            stepData.put("pressure", pressure);
            stepData.put("delta", delta);
            stepData.put("decay", decay);
            stepData.put("tokens", work.getTokens());
            stepData.put("tool_calls", work.getToolCalls());
            stepData.put("depth", work.getDepth());
            stepData.put("tag", work.getTag());

            double pressureNow = pressure;
            double releaseThr = cfg.getReleaseThreshold();
            double escThr = cfg.getEscalationThreshold();
            boolean postReleaseLock = cfg.isPostReleaseLock();

            emit("engine.step", stepData);

            if (pressureNow >= releaseThr) {
                Map<String, Object> rd = new LinkedHashMap<>();
                rd.put("pressure", pressureNow);
                rd.put("threshold", releaseThr);
                emit("engine.release", rd);
                this.pressure = 0.0;
                if (postReleaseLock) {
                    this.lifecycle = Lifecycle.LOCKED;
                    Map<String, Object> ld = new LinkedHashMap<>();
                    ld.put("reason", "post_release_lock");
                    emit("engine.locked", ld);
                } else {
                    this.lifecycle = Lifecycle.RUNNING;
                }
                return StepOutcome.RELEASED;
            }
            if (pressureNow >= escThr) {
                this.lifecycle = Lifecycle.ESCALATED;
                Map<String, Object> ed = new LinkedHashMap<>();
                ed.put("pressure", pressureNow);
                ed.put("threshold", escThr);
                emit("engine.escalation", ed);
                return StepOutcome.ESCALATED;
            }
            return StepOutcome.OK;
        } finally {
            lock.unlock();
        }
    }

    /** Reset the engine. Emits {@code engine.reset}. */
    public PressureSnapshot reset() {
        lock.lock();
        try {
            this.pressure = 0.0;
            this.step = 0L;
            this.lastDelta = 0.0;
            this.lastStepAt = clock.now();
            this.lifecycle = Lifecycle.INIT;
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("pressure", 0.0);
            emit("engine.reset", data);
            return new PressureSnapshot(pressure, step, lifecycle, lastDelta, lastStepAt);
        } finally {
            lock.unlock();
        }
    }

    private void emit(String kind, Map<String, Object> data) {
        audit.emit(new Event(executionId, kind, timestampClock.now(), data));
    }

    private static double clamp01(double v) {
        if (v < 0.0) return 0.0;
        if (v > 1.0) return 1.0;
        return v;
    }
}

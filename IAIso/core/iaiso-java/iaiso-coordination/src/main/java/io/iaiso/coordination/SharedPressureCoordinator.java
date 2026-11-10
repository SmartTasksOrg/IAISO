package io.iaiso.coordination;

import io.iaiso.audit.Event;
import io.iaiso.audit.NullSink;
import io.iaiso.audit.Sink;
import io.iaiso.policy.Aggregator;
import io.iaiso.policy.SumAggregator;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Consumer;

/**
 * In-memory coordinator that aggregates pressure across a single
 * process's executions.
 */
public class SharedPressureCoordinator {

    @FunctionalInterface
    public interface Clock {
        double now();
        static Clock wallclock() {
            return () -> System.currentTimeMillis() / 1000.0;
        }
    }

    private final String coordinatorId;
    private final double escalationThreshold;
    private final double releaseThreshold;
    private final double notifyCooldownSeconds;
    private final Aggregator aggregator;
    private final Sink auditSink;
    private final Consumer<Snapshot> onEscalation;  // nullable
    private final Consumer<Snapshot> onRelease;     // nullable
    private final Clock clock;
    private final ReentrantLock lock = new ReentrantLock();

    // mutable
    private final Map<String, Double> pressures = new TreeMap<>();
    private CoordinatorLifecycle lifecycle = CoordinatorLifecycle.NOMINAL;
    private double lastNotifyAt = 0.0;

    SharedPressureCoordinator(String coordinatorId, double escalationThreshold,
                              double releaseThreshold, double notifyCooldownSeconds,
                              Aggregator aggregator, Sink auditSink,
                              Consumer<Snapshot> onEscalation,
                              Consumer<Snapshot> onRelease,
                              Clock clock,
                              boolean emitInit) {
        if (releaseThreshold <= escalationThreshold) {
            throw new CoordinatorException(
                "release_threshold must exceed escalation_threshold ("
                + releaseThreshold + " <= " + escalationThreshold + ")");
        }
        this.coordinatorId = coordinatorId;
        this.escalationThreshold = escalationThreshold;
        this.releaseThreshold = releaseThreshold;
        this.notifyCooldownSeconds = notifyCooldownSeconds;
        this.aggregator = aggregator;
        this.auditSink = auditSink != null ? auditSink : NullSink.INSTANCE;
        this.onEscalation = onEscalation;
        this.onRelease = onRelease;
        this.clock = clock != null ? clock : Clock.wallclock();
        if (emitInit) {
            emitInit("memory");
        }
    }

    public static Builder builder() { return new Builder(); }

    public String getCoordinatorId() { return coordinatorId; }
    public Aggregator getAggregator() { return aggregator; }

    /** Register an execution with pressure 0. */
    public Snapshot register(String executionId) {
        lock.lock();
        try {
            pressures.put(executionId, 0.0);
        } finally {
            lock.unlock();
        }
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("execution_id", executionId);
        emit("coordinator.execution_registered", data);
        return snapshot();
    }

    public Snapshot unregister(String executionId) {
        lock.lock();
        try {
            pressures.remove(executionId);
        } finally {
            lock.unlock();
        }
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("execution_id", executionId);
        emit("coordinator.execution_unregistered", data);
        return snapshot();
    }

    /** Update pressure for an execution and re-evaluate lifecycle. */
    public Snapshot update(String executionId, double pressure) {
        if (pressure < 0.0 || pressure > 1.0) {
            throw new CoordinatorException(
                "pressure must be in [0, 1], got " + pressure);
        }
        lock.lock();
        try {
            pressures.put(executionId, pressure);
        } finally {
            lock.unlock();
        }
        return evaluate();
    }

    public int reset() {
        int count;
        lock.lock();
        try {
            count = pressures.size();
            pressures.replaceAll((k, v) -> 0.0);
            lifecycle = CoordinatorLifecycle.NOMINAL;
        } finally {
            lock.unlock();
        }
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("fleet_size", count);
        emit("coordinator.reset", data);
        return count;
    }

    public Snapshot snapshot() {
        lock.lock();
        try {
            double agg = aggregator.aggregate(pressures);
            return new Snapshot(coordinatorId, agg, lifecycle,
                pressures.size(), pressures);
        } finally {
            lock.unlock();
        }
    }

    /** Replace per-execution pressures wholesale. Used by Redis variant. */
    void setPressuresFromMap(Map<String, Double> updated) {
        lock.lock();
        try {
            pressures.clear();
            pressures.putAll(updated);
        } finally {
            lock.unlock();
        }
    }

    Snapshot evaluate() {
        double now = clock.now();
        double agg;
        CoordinatorLifecycle prior;
        CoordinatorLifecycle next;
        boolean inCooldown;
        lock.lock();
        try {
            agg = aggregator.aggregate(pressures);
            prior = lifecycle;
            inCooldown = (now - lastNotifyAt) < notifyCooldownSeconds;
            if (agg >= releaseThreshold) {
                next = CoordinatorLifecycle.RELEASED;
            } else if (agg >= escalationThreshold) {
                next = prior == CoordinatorLifecycle.NOMINAL
                    ? CoordinatorLifecycle.ESCALATED
                    : prior;
            } else {
                next = CoordinatorLifecycle.NOMINAL;
            }
            lifecycle = next;
        } finally {
            lock.unlock();
        }
        if (next != prior && !inCooldown) {
            switch (next) {
                case RELEASED: {
                    Map<String, Object> data = new LinkedHashMap<>();
                    data.put("aggregate_pressure", agg);
                    data.put("threshold", releaseThreshold);
                    emit("coordinator.release", data);
                    setLastNotifyAt(now);
                    if (onRelease != null) onRelease.accept(snapshot());
                    break;
                }
                case ESCALATED: {
                    Map<String, Object> data = new LinkedHashMap<>();
                    data.put("aggregate_pressure", agg);
                    data.put("threshold", escalationThreshold);
                    emit("coordinator.escalation", data);
                    setLastNotifyAt(now);
                    if (onEscalation != null) onEscalation.accept(snapshot());
                    break;
                }
                case NOMINAL: {
                    Map<String, Object> data = new LinkedHashMap<>();
                    data.put("aggregate_pressure", agg);
                    emit("coordinator.returned_to_nominal", data);
                    setLastNotifyAt(now);
                    break;
                }
            }
        }
        return snapshot();
    }

    private void setLastNotifyAt(double t) {
        lock.lock();
        try { lastNotifyAt = t; } finally { lock.unlock(); }
    }

    private void emitInit(String backend) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("coordinator_id", coordinatorId);
        data.put("aggregator", aggregator.name());
        data.put("backend", backend);
        emit("coordinator.init", data);
    }

    private void emit(String kind, Map<String, Object> data) {
        Event e = new Event("coord:" + coordinatorId, kind, clock.now(), data);
        auditSink.emit(e);
    }

    public static final class Builder {
        String coordinatorId = "default";
        double escalationThreshold = 5.0;
        double releaseThreshold = 8.0;
        double notifyCooldownSeconds = 1.0;
        Aggregator aggregator = new SumAggregator();
        Sink auditSink;
        Consumer<Snapshot> onEscalation;
        Consumer<Snapshot> onRelease;
        Clock clock;

        public Builder coordinatorId(String v) { this.coordinatorId = v; return this; }
        public Builder escalationThreshold(double v) { this.escalationThreshold = v; return this; }
        public Builder releaseThreshold(double v) { this.releaseThreshold = v; return this; }
        public Builder notifyCooldownSeconds(double v) { this.notifyCooldownSeconds = v; return this; }
        public Builder aggregator(Aggregator v) { this.aggregator = v; return this; }
        public Builder auditSink(Sink v) { this.auditSink = v; return this; }
        public Builder onEscalation(Consumer<Snapshot> v) { this.onEscalation = v; return this; }
        public Builder onRelease(Consumer<Snapshot> v) { this.onRelease = v; return this; }
        public Builder clock(Clock v) { this.clock = v; return this; }

        public SharedPressureCoordinator build() {
            return new SharedPressureCoordinator(coordinatorId, escalationThreshold,
                releaseThreshold, notifyCooldownSeconds, aggregator, auditSink,
                onEscalation, onRelease, clock, true);
        }
    }
}

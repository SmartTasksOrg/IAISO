package io.iaiso.metrics;

import io.iaiso.audit.Event;
import io.iaiso.audit.Sink;

/**
 * IAIso Prometheus metrics sink.
 *
 * <p>Structurally typed — this module doesn't depend on any specific
 * Prometheus client library. The official {@code prometheus-simpleclient}
 * and {@code prometheus-metrics} libraries satisfy these interfaces with
 * thin adapters.
 *
 * <p>Suggested histogram buckets for {@code iaiso_step_delta}:
 * see {@link #SUGGESTED_HISTOGRAM_BUCKETS}.
 */
public final class PrometheusSink implements Sink {

    /** Suggested histogram buckets for {@code iaiso_step_delta}. */
    public static final double[] SUGGESTED_HISTOGRAM_BUCKETS =
        {0.0, 0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0};

    public interface Counter { void inc(); }
    public interface CounterVec { Counter labels(String... values); }
    public interface Gauge { void set(double v); }
    public interface GaugeVec { Gauge labels(String... values); }
    public interface Histogram { void observe(double v); }

    private final CounterVec events;
    private final Counter escalations;
    private final Counter releases;
    private final GaugeVec pressure;
    private final Histogram stepDelta;

    public PrometheusSink(CounterVec events, Counter escalations, Counter releases,
                          GaugeVec pressure, Histogram stepDelta) {
        this.events = events;
        this.escalations = escalations;
        this.releases = releases;
        this.pressure = pressure;
        this.stepDelta = stepDelta;
    }

    @Override
    public void emit(Event event) {
        if (events != null) events.labels(event.getKind()).inc();
        switch (event.getKind()) {
            case "engine.escalation":
                if (escalations != null) escalations.inc();
                break;
            case "engine.release":
                if (releases != null) releases.inc();
                break;
            case "engine.step":
                Object p = event.getData().get("pressure");
                if (pressure != null && p instanceof Number) {
                    pressure.labels(event.getExecutionId()).set(((Number) p).doubleValue());
                }
                Object d = event.getData().get("delta");
                if (stepDelta != null && d instanceof Number) {
                    stepDelta.observe(((Number) d).doubleValue());
                }
                break;
            default:
                // ignore
        }
    }
}

package io.iaiso.policy;

import java.util.Map;

/** Arithmetic mean of per-execution pressures. */
public final class MeanAggregator implements Aggregator {
    @Override public String name() { return "mean"; }
    @Override public double aggregate(Map<String, Double> p) {
        if (p.isEmpty()) return 0.0;
        double total = 0.0;
        for (Double v : p.values()) total += v;
        return total / p.size();
    }
}

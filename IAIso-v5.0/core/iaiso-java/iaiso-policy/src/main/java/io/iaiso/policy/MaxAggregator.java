package io.iaiso.policy;

import java.util.Map;

/** Maximum of per-execution pressures. */
public final class MaxAggregator implements Aggregator {
    @Override public String name() { return "max"; }
    @Override public double aggregate(Map<String, Double> p) {
        double max = 0.0;
        for (Double v : p.values()) {
            if (v > max) max = v;
        }
        return max;
    }
}

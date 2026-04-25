package io.iaiso.policy;

import java.util.Collections;
import java.util.Map;

/** Sum of per-execution pressures. */
public final class SumAggregator implements Aggregator {
    @Override public String name() { return "sum"; }
    @Override public double aggregate(Map<String, Double> p) {
        double total = 0.0;
        for (Double v : p.values()) total += v;
        return total;
    }
}

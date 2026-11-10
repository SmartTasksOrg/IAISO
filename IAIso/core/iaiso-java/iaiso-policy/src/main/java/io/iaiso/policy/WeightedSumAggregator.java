package io.iaiso.policy;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/** Weighted sum of per-execution pressures. */
public final class WeightedSumAggregator implements Aggregator {
    private final Map<String, Double> weights;
    private final double defaultWeight;

    public WeightedSumAggregator(Map<String, Double> weights, double defaultWeight) {
        this.weights = Collections.unmodifiableMap(new HashMap<>(weights));
        this.defaultWeight = defaultWeight;
    }

    @Override public String name() { return "weighted_sum"; }

    @Override public double aggregate(Map<String, Double> p) {
        double total = 0.0;
        for (Map.Entry<String, Double> e : p.entrySet()) {
            double w = weights.getOrDefault(e.getKey(), defaultWeight);
            total += w * e.getValue();
        }
        return total;
    }

    public Map<String, Double> getWeights() { return weights; }
    public double getDefaultWeight() { return defaultWeight; }
}

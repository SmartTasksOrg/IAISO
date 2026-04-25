package io.iaiso.policy;

import java.util.Map;

/** A coordinator aggregation strategy. */
public interface Aggregator {

    /** Wire-format aggregator name. */
    String name();

    /** Compute the aggregate from per-execution pressures. */
    double aggregate(Map<String, Double> pressures);
}

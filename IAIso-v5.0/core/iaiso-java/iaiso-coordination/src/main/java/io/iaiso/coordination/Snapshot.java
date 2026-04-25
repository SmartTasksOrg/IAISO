package io.iaiso.coordination;

import java.util.Collections;
import java.util.Map;
import java.util.TreeMap;

/** Read-only view of coordinator state. */
public final class Snapshot {
    private final String coordinatorId;
    private final double aggregatePressure;
    private final CoordinatorLifecycle lifecycle;
    private final int activeExecutions;
    private final Map<String, Double> perExecution;

    public Snapshot(String coordinatorId, double aggregatePressure,
                    CoordinatorLifecycle lifecycle, int activeExecutions,
                    Map<String, Double> perExecution) {
        this.coordinatorId = coordinatorId;
        this.aggregatePressure = aggregatePressure;
        this.lifecycle = lifecycle;
        this.activeExecutions = activeExecutions;
        this.perExecution = Collections.unmodifiableMap(new TreeMap<>(perExecution));
    }

    public String getCoordinatorId() { return coordinatorId; }
    public double getAggregatePressure() { return aggregatePressure; }
    public CoordinatorLifecycle getLifecycle() { return lifecycle; }
    public int getActiveExecutions() { return activeExecutions; }
    public Map<String, Double> getPerExecution() { return perExecution; }
}

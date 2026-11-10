package io.iaiso.coordination;

/** Lifecycle state of a fleet-aggregated coordinator. */
public enum CoordinatorLifecycle {
    NOMINAL("nominal"),
    ESCALATED("escalated"),
    RELEASED("released");

    private final String wireValue;
    CoordinatorLifecycle(String w) { this.wireValue = w; }
    @Override public String toString() { return wireValue; }
}

package io.iaiso.core;

/**
 * The result of a single {@code step()} call. Wire-format strings,
 * lowercase, matching the other reference SDKs exactly.
 */
public enum StepOutcome {
    OK("ok"),
    ESCALATED("escalated"),
    RELEASED("released"),
    LOCKED("locked");

    private final String wireValue;

    StepOutcome(String wireValue) {
        this.wireValue = wireValue;
    }

    @Override
    public String toString() {
        return wireValue;
    }

    public static StepOutcome fromWire(String s) {
        for (StepOutcome o : values()) {
            if (o.wireValue.equals(s)) {
                return o;
            }
        }
        throw new IllegalArgumentException("unknown step outcome: " + s);
    }
}

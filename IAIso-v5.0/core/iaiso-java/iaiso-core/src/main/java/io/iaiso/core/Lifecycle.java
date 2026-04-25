package io.iaiso.core;

/**
 * The engine's high-level lifecycle state.
 * <p>
 * Wire-format strings (returned by {@link #toString()}) MUST match the
 * Python, Node, Go, and Rust reference SDKs exactly. The ordinal positions
 * are not part of the wire format — only the lowercase names.
 */
public enum Lifecycle {
    INIT("init"),
    RUNNING("running"),
    ESCALATED("escalated"),
    RELEASED("released"),
    LOCKED("locked");

    private final String wireValue;

    Lifecycle(String wireValue) {
        this.wireValue = wireValue;
    }

    /** Lowercase wire-format string, e.g. {@code "running"}. */
    @Override
    public String toString() {
        return wireValue;
    }

    /** Parse a wire-format string back into a {@link Lifecycle}. */
    public static Lifecycle fromWire(String s) {
        for (Lifecycle l : values()) {
            if (l.wireValue.equals(s)) {
                return l;
            }
        }
        throw new IllegalArgumentException("unknown lifecycle: " + s);
    }
}

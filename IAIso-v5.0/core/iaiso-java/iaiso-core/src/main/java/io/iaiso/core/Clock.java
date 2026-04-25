package io.iaiso.core;

/**
 * A clock returning fractional seconds. Tests pass scripted clocks for
 * deterministic evaluation.
 */
@FunctionalInterface
public interface Clock {
    /** Current time, in fractional seconds. */
    double now();

    /** A wallclock based on {@link System#currentTimeMillis()} and
     * nanoseconds for sub-millisecond resolution. */
    static Clock wallclock() {
        return () -> {
            long millis = System.currentTimeMillis();
            // Sub-millisecond precision via nanoTime for the fractional part
            return millis / 1000.0 + (System.nanoTime() % 1_000_000) / 1e9;
        };
    }
}

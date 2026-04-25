package io.iaiso.audit;

/**
 * The interface every audit sink implements.
 * <p>
 * Implementations SHOULD make {@code emit} non-blocking on the agent's
 * hot path — sustained backpressure is signaled by dropping rather
 * than throwing. See {@code spec/events/README.md §6} for normative
 * delivery semantics.
 */
@FunctionalInterface
public interface Sink {
    void emit(Event event);
}

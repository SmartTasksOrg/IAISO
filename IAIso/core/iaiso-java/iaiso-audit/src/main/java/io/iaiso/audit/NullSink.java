package io.iaiso.audit;

/** A sink that discards every event. */
public final class NullSink implements Sink {
    public static final NullSink INSTANCE = new NullSink();
    @Override public void emit(Event event) { /* no-op */ }
}

package io.iaiso.audit;

/** A sink that writes one JSON event per line to {@code System.out}. */
public final class StdoutSink implements Sink {
    public static final StdoutSink INSTANCE = new StdoutSink();
    @Override
    public void emit(Event event) {
        System.out.println(event.toJson());
    }
}

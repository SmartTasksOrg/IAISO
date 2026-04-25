package io.iaiso.audit;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** A sink that broadcasts every event to a list of children. */
public final class FanoutSink implements Sink {
    private final List<Sink> sinks;

    public FanoutSink(Sink... sinks) {
        this.sinks = Collections.unmodifiableList(Arrays.asList(sinks));
    }

    public FanoutSink(List<Sink> sinks) {
        this.sinks = Collections.unmodifiableList(sinks);
    }

    @Override
    public void emit(Event event) {
        for (Sink s : sinks) {
            s.emit(event);
        }
    }

    public List<Sink> sinks() {
        return sinks;
    }
}

package io.iaiso.audit;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.locks.ReentrantLock;

/** A sink that records emitted events in memory. Useful for tests. */
public final class MemorySink implements Sink {
    private final List<Event> events = new ArrayList<>();
    private final ReentrantLock lock = new ReentrantLock();

    @Override
    public void emit(Event event) {
        lock.lock();
        try {
            events.add(event);
        } finally {
            lock.unlock();
        }
    }

    /** Snapshot of recorded events. */
    public List<Event> events() {
        lock.lock();
        try {
            return Collections.unmodifiableList(new ArrayList<>(events));
        } finally {
            lock.unlock();
        }
    }

    public void clear() {
        lock.lock();
        try {
            events.clear();
        } finally {
            lock.unlock();
        }
    }
}

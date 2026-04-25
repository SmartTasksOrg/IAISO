package io.iaiso.audit;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.concurrent.locks.ReentrantLock;

/**
 * A sink that appends one JSON event per line to a file.
 * <p>
 * Errors are silently dropped — best-effort delivery semantics
 * specified in {@code spec/events/README.md §6}.
 */
public final class JsonlFileSink implements Sink {
    private final Path path;
    private final ReentrantLock lock = new ReentrantLock();

    public JsonlFileSink(Path path) {
        this.path = path;
    }

    @Override
    public void emit(Event event) {
        lock.lock();
        try {
            String line = event.toJson() + "\n";
            Files.writeString(path, line, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException ignored) {
            // best-effort
        } finally {
            lock.unlock();
        }
    }
}

package io.iaiso.core;

import io.iaiso.audit.Event;
import io.iaiso.audit.NullSink;
import io.iaiso.audit.Sink;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * High-level execution facade. Composes a {@link PressureEngine} with
 * an audit sink and lifecycle management.
 *
 * <p>Use {@link #run(BoundedExecutionOptions, ExecutionBody)} for the
 * try-with-resources / closure style, which guarantees
 * {@code execution.closed} is emitted even on exceptions:
 *
 * <pre>{@code
 * BoundedExecution.run(opts, exec -> {
 *     exec.recordToolCall("search", 500);
 * });
 * }</pre>
 */
public final class BoundedExecution implements AutoCloseable {

    /** A unit of work to run inside a bounded execution. */
    @FunctionalInterface
    public interface ExecutionBody {
        void run(BoundedExecution execution);
    }

    private final PressureEngine engine;
    private final Sink auditSink;
    private final Clock timestampClock;
    private final AtomicBoolean closed = new AtomicBoolean(false);

    private BoundedExecution(BoundedExecutionOptions opts) {
        String execId = opts.getExecutionId();
        if (execId == null || execId.isEmpty()) {
            execId = "exec-" + Long.toHexString(System.nanoTime());
        }
        Clock clk = opts.getClock() != null ? opts.getClock() : Clock.wallclock();
        Clock tsClk = opts.getTimestampClock() != null ? opts.getTimestampClock() : clk;
        this.auditSink = opts.getAuditSink() != null ? opts.getAuditSink() : NullSink.INSTANCE;
        this.timestampClock = tsClk;
        this.engine = new PressureEngine(opts.getConfig(),
            EngineOptions.builder()
                .executionId(execId)
                .auditSink(this.auditSink)
                .clock(clk)
                .timestampClock(tsClk)
                .build());
    }

    /** Construct a {@code BoundedExecution}. The caller MUST {@link #close()} it. */
    public static BoundedExecution start(BoundedExecutionOptions opts) {
        return new BoundedExecution(opts);
    }

    /** Run a closure inside a bounded execution; closes on exit. */
    public static void run(BoundedExecutionOptions opts, ExecutionBody body) {
        boolean errored = false;
        BoundedExecution exec = null;
        try {
            exec = start(opts);
            body.run(exec);
        } catch (RuntimeException e) {
            errored = true;
            throw e;
        } finally {
            if (exec != null) {
                exec.closeWith(errored);
            }
        }
    }

    public PressureEngine getEngine() { return engine; }
    public PressureSnapshot snapshot() { return engine.snapshot(); }

    /** Account for tokens with an optional tag. */
    public StepOutcome recordTokens(long tokens, String tag) {
        return account(StepInput.builder().tokens(tokens).tag(tag).build());
    }

    /** Account for a single tool invocation. */
    public StepOutcome recordToolCall(String name, long tokens) {
        return account(StepInput.builder()
            .tokens(tokens)
            .toolCalls(1)
            .tag(name)
            .build());
    }

    /** General step accounting. */
    public StepOutcome recordStep(StepInput work) {
        return account(work);
    }

    private StepOutcome account(StepInput work) {
        StepOutcome o = engine.step(work);
        return o;
    }

    /** Pre-check the engine state without advancing it. */
    public StepOutcome check() {
        switch (engine.getLifecycle()) {
            case LOCKED: return StepOutcome.LOCKED;
            case ESCALATED: return StepOutcome.ESCALATED;
            default: return StepOutcome.OK;
        }
    }

    public PressureSnapshot reset() { return engine.reset(); }

    /** Close the execution, emitting {@code execution.closed}. Idempotent. */
    @Override
    public void close() {
        closeWith(false);
    }

    private void closeWith(boolean errored) {
        if (!closed.compareAndSet(false, true)) return;
        PressureSnapshot snap = engine.snapshot();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("final_pressure", snap.getPressure());
        data.put("final_lifecycle", snap.getLifecycle().toString());
        data.put("exception", errored ? "error" : null);
        auditSink.emit(new Event(engine.getExecutionId(), "execution.closed",
            timestampClock.now(), data));
    }
}

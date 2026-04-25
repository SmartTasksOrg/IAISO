package io.iaiso.core;

import io.iaiso.audit.Sink;

/** Options for {@link BoundedExecution#start(BoundedExecutionOptions)}. */
public final class BoundedExecutionOptions {
    private final String executionId;
    private final PressureConfig config;
    private final Sink auditSink;
    private final Clock clock;
    private final Clock timestampClock;

    private BoundedExecutionOptions(Builder b) {
        this.executionId = b.executionId;
        this.config = b.config;
        this.auditSink = b.auditSink;
        this.clock = b.clock;
        this.timestampClock = b.timestampClock;
    }

    public String getExecutionId() { return executionId; }
    public PressureConfig getConfig() { return config; }
    public Sink getAuditSink() { return auditSink; }
    public Clock getClock() { return clock; }
    public Clock getTimestampClock() { return timestampClock; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String executionId;
        private PressureConfig config = PressureConfig.defaults();
        private Sink auditSink;
        private Clock clock;
        private Clock timestampClock;

        public Builder executionId(String v) { this.executionId = v; return this; }
        public Builder config(PressureConfig v) { this.config = v; return this; }
        public Builder auditSink(Sink v) { this.auditSink = v; return this; }
        public Builder clock(Clock v) { this.clock = v; return this; }
        public Builder timestampClock(Clock v) { this.timestampClock = v; return this; }

        public BoundedExecutionOptions build() { return new BoundedExecutionOptions(this); }
    }
}

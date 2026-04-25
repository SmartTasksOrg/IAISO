package io.iaiso.core;

import io.iaiso.audit.Sink;

/** Options for {@link PressureEngine}. */
public final class EngineOptions {
    private final String executionId;
    private final Sink auditSink;
    private final Clock clock;
    private final Clock timestampClock;

    private EngineOptions(Builder b) {
        this.executionId = b.executionId;
        this.auditSink = b.auditSink;
        this.clock = b.clock;
        this.timestampClock = b.timestampClock;
    }

    public String getExecutionId() { return executionId; }
    public Sink getAuditSink() { return auditSink; }
    public Clock getClock() { return clock; }
    public Clock getTimestampClock() { return timestampClock; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String executionId = "exec-default";
        private Sink auditSink;
        private Clock clock;
        private Clock timestampClock;

        public Builder executionId(String v) { this.executionId = v; return this; }
        public Builder auditSink(Sink v) { this.auditSink = v; return this; }
        public Builder clock(Clock v) { this.clock = v; return this; }
        public Builder timestampClock(Clock v) { this.timestampClock = v; return this; }

        public EngineOptions build() { return new EngineOptions(this); }
    }
}

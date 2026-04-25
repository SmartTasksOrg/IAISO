package io.iaiso.core;

/** Work unit accounted for in a single {@code step()} call. */
public final class StepInput {
    private final long tokens;
    private final long toolCalls;
    private final long depth;
    private final String tag;

    private StepInput(Builder b) {
        this.tokens = b.tokens;
        this.toolCalls = b.toolCalls;
        this.depth = b.depth;
        this.tag = b.tag;
    }

    public long getTokens() { return tokens; }
    public long getToolCalls() { return toolCalls; }
    public long getDepth() { return depth; }
    public String getTag() { return tag; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private long tokens;
        private long toolCalls;
        private long depth;
        private String tag;

        public Builder tokens(long v) { this.tokens = v; return this; }
        public Builder toolCalls(long v) { this.toolCalls = v; return this; }
        public Builder depth(long v) { this.depth = v; return this; }
        public Builder tag(String v) { this.tag = v; return this; }

        public StepInput build() { return new StepInput(this); }
    }
}

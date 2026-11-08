package io.iaiso.core;

/** Work unit accounted for in a single {@code step()} call. */
public final class StepInput {
    private final long tokens;
    private final long toolCalls;
    private final long depth;
    private final String tag;

    private StepInput(Builder b) {
        // A negative count would lower pressure. Refuse it at construction.
        requireNonNegative("tokens", b.tokens);
        requireNonNegative("toolCalls", b.toolCalls);
        requireNonNegative("depth", b.depth);
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

    /**
     * Build from an untyped map, as produced by a JSON library (snake_case keys).
     * Counts must be integral boxed types; Double, Boolean, String and null are
     * refused rather than truncated or parsed. Unknown keys are refused.
     */
    public static StepInput fromMap(java.util.Map<String, ?> m) {
        Builder b = builder();
        for (java.util.Map.Entry<String, ?> e : m.entrySet()) {
            String k = e.getKey();
            Object v = e.getValue();
            switch (k) {
                case "tokens": b.tokens(count(k, v)); break;
                case "tool_calls": b.toolCalls(count(k, v)); break;
                case "depth": b.depth(count(k, v)); break;
                case "tag":
                    if (v != null && !(v instanceof String)) {
                        throw new IllegalArgumentException("StepInput.tag must be a string or null");
                    }
                    b.tag((String) v);
                    break;
                default:
                    throw new IllegalArgumentException("StepInput: unknown field " + k);
            }
        }
        return b.build();
    }

    private static long count(String name, Object v) {
        if (v instanceof Long || v instanceof Integer || v instanceof Short || v instanceof Byte) {
            return ((Number) v).longValue();
        }
        throw new IllegalArgumentException("StepInput." + name
            + " must be a non-negative integer, got " + (v == null ? "null" : v.getClass().getSimpleName()));
    }

    private static void requireNonNegative(String name, long v) {
        if (v < 0) {
            throw new IllegalArgumentException("StepInput." + name + " must be >= 0, got " + v);
        }
    }

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

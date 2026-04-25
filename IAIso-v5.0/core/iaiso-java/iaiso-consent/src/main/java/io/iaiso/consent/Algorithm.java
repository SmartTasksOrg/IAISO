package io.iaiso.consent;

/** Supported JWT signing algorithms. {@code none} is intentionally absent. */
public enum Algorithm {
    HS256("HS256"),
    RS256("RS256");

    private final String wireName;
    Algorithm(String w) { this.wireName = w; }
    public String wireName() { return wireName; }

    public static Algorithm fromWire(String s) {
        for (Algorithm a : values()) {
            if (a.wireName.equals(s)) return a;
        }
        throw new IllegalArgumentException("unsupported algorithm: " + s);
    }
}

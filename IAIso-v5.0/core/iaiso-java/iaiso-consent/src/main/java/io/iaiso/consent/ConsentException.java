package io.iaiso.consent;

/** Base type for consent verification failures. */
public abstract class ConsentException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    protected ConsentException(String message) { super(message); }
    protected ConsentException(String message, Throwable cause) { super(message, cause); }

    /** The JWT failed signature, format, or claim validation. */
    public static final class InvalidToken extends ConsentException {
        private static final long serialVersionUID = 1L;
        public InvalidToken(String message) { super(message); }
        public InvalidToken(String message, Throwable cause) { super(message, cause); }
    }

    /** The token's {@code exp} claim is in the past (after leeway). */
    public static final class ExpiredToken extends ConsentException {
        private static final long serialVersionUID = 1L;
        public ExpiredToken() { super("expired token"); }
    }

    /** The token's {@code jti} is on the revocation list. */
    public static final class RevokedToken extends ConsentException {
        private static final long serialVersionUID = 1L;
        private final String jti;
        public RevokedToken(String jti) { super("revoked token: jti=" + jti); this.jti = jti; }
        public String getJti() { return jti; }
    }
}

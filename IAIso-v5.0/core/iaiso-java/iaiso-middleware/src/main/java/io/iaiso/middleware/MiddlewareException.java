package io.iaiso.middleware;

/** Base type for middleware-induced failures. */
public abstract class MiddlewareException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    protected MiddlewareException(String message) { super(message); }
    protected MiddlewareException(String message, Throwable cause) { super(message, cause); }

    /** Raised when {@code raiseOnEscalation} is true and the engine has escalated. */
    public static final class EscalationRaised extends MiddlewareException {
        private static final long serialVersionUID = 1L;
        public EscalationRaised() { super("execution escalated; raise-on-escalation enabled"); }
    }

    /** Raised when the execution is locked. */
    public static final class Locked extends MiddlewareException {
        private static final long serialVersionUID = 1L;
        public Locked() { super("execution locked"); }
    }

    /** Raised when the upstream provider call failed. */
    public static final class Provider extends MiddlewareException {
        private static final long serialVersionUID = 1L;
        public Provider(String message) { super("provider error: " + message); }
        public Provider(String message, Throwable cause) {
            super("provider error: " + message, cause);
        }
    }
}

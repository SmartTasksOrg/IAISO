package io.iaiso.policy;

/** Wraps a policy validation failure with a JSON-Pointer-like path. */
public class PolicyException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    public PolicyException(String message) { super(message); }
    public PolicyException(String message, Throwable cause) { super(message, cause); }
}

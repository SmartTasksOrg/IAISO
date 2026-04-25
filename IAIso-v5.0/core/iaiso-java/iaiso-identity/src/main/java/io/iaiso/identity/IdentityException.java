package io.iaiso.identity;

public class IdentityException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    public IdentityException(String message) { super(message); }
    public IdentityException(String message, Throwable cause) { super(message, cause); }
}

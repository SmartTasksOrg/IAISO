package io.iaiso.coordination;

public class CoordinatorException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    public CoordinatorException(String message) { super(message); }
    public CoordinatorException(String message, Throwable cause) { super(message, cause); }
}

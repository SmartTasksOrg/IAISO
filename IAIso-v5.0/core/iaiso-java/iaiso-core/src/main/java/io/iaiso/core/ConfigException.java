package io.iaiso.core;

/** Thrown when a {@link PressureConfig} fails validation. */
public class ConfigException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    public ConfigException(String message) {
        super(message);
    }
}

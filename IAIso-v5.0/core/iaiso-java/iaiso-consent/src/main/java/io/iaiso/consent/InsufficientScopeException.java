package io.iaiso.consent;

import java.util.Collections;
import java.util.List;

/** Thrown when a scope check fails. */
public class InsufficientScopeException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    private final List<String> granted;
    private final String requested;

    public InsufficientScopeException(List<String> granted, String requested) {
        super("scope " + requested + " not granted by token (granted: " +
            String.join(", ", granted) + ")");
        this.granted = Collections.unmodifiableList(granted);
        this.requested = requested;
    }

    public List<String> getGranted() { return granted; }
    public String getRequested() { return requested; }
}

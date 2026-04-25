package io.iaiso.consent;

import com.google.gson.JsonObject;

import java.util.Collections;
import java.util.List;

/** A verified consent scope, ready to attach to an execution. */
public final class Scope {
    private final String token;
    private final String subject;
    private final List<String> scopes;
    private final String executionId;   // nullable
    private final String jti;
    private final long issuedAt;
    private final long expiresAt;
    private final JsonObject metadata;

    public Scope(String token, String subject, List<String> scopes,
                 String executionId, String jti, long issuedAt, long expiresAt,
                 JsonObject metadata) {
        this.token = token;
        this.subject = subject;
        this.scopes = Collections.unmodifiableList(scopes);
        this.executionId = executionId;
        this.jti = jti;
        this.issuedAt = issuedAt;
        this.expiresAt = expiresAt;
        this.metadata = metadata != null ? metadata : new JsonObject();
    }

    public String getToken() { return token; }
    public String getSubject() { return subject; }
    public List<String> getScopes() { return scopes; }
    public String getExecutionId() { return executionId; }
    public String getJti() { return jti; }
    public long getIssuedAt() { return issuedAt; }
    public long getExpiresAt() { return expiresAt; }
    public JsonObject getMetadata() { return metadata; }

    /** Does the scope grant the requested string? */
    public boolean grants(String requested) {
        return Scopes.granted(scopes, requested);
    }

    /** Throws {@link InsufficientScopeException} if not granted. */
    public void require(String requested) {
        if (!grants(requested)) {
            throw new InsufficientScopeException(scopes, requested);
        }
    }
}

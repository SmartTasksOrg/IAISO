package io.iaiso.policy;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Consent-section configuration from a parsed policy. */
public final class ConsentPolicy {
    private final String issuer;  // nullable
    private final double defaultTtlSeconds;
    private final List<String> requiredScopes;
    private final List<String> allowedAlgorithms;

    public ConsentPolicy(String issuer, double defaultTtlSeconds,
                         List<String> requiredScopes, List<String> allowedAlgorithms) {
        this.issuer = issuer;
        this.defaultTtlSeconds = defaultTtlSeconds;
        this.requiredScopes = Collections.unmodifiableList(requiredScopes);
        this.allowedAlgorithms = Collections.unmodifiableList(allowedAlgorithms);
    }

    public static ConsentPolicy defaults() {
        return new ConsentPolicy(null, 3600.0,
            Collections.emptyList(),
            Arrays.asList("HS256", "RS256"));
    }

    public String getIssuer() { return issuer; }
    public double getDefaultTtlSeconds() { return defaultTtlSeconds; }
    public List<String> getRequiredScopes() { return requiredScopes; }
    public List<String> getAllowedAlgorithms() { return allowedAlgorithms; }
}

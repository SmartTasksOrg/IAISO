package io.iaiso.identity;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Configuration for an {@link OidcVerifier}. */
public final class ProviderConfig {
    public final String discoveryUrl;       // nullable
    public final String jwksUrl;            // nullable
    public final String issuer;             // nullable — empty means trust discovery
    public final String audience;           // nullable — empty disables aud check
    public final List<String> allowedAlgorithms;
    public final long leewaySeconds;

    public ProviderConfig(String discoveryUrl, String jwksUrl, String issuer, String audience,
                          List<String> allowedAlgorithms, long leewaySeconds) {
        this.discoveryUrl = discoveryUrl;
        this.jwksUrl = jwksUrl;
        this.issuer = issuer;
        this.audience = audience;
        this.allowedAlgorithms = Collections.unmodifiableList(
            allowedAlgorithms != null ? allowedAlgorithms : Arrays.asList("RS256"));
        this.leewaySeconds = leewaySeconds;
    }

    public static ProviderConfig defaults() {
        return new ProviderConfig(null, null, null, null, Arrays.asList("RS256"), 5);
    }

    /** Build a {@link ProviderConfig} for Okta. */
    public static ProviderConfig okta(String domain, String audience) {
        return new ProviderConfig(
            "https://" + domain + "/.well-known/openid-configuration",
            null,
            "https://" + domain,
            audience,
            Arrays.asList("RS256"),
            5);
    }

    /** Build a {@link ProviderConfig} for Auth0. */
    public static ProviderConfig auth0(String domain, String audience) {
        return new ProviderConfig(
            "https://" + domain + "/.well-known/openid-configuration",
            null,
            "https://" + domain + "/",
            audience,
            Arrays.asList("RS256"),
            5);
    }

    /** Build a {@link ProviderConfig} for Azure AD / Entra. */
    public static ProviderConfig azureAd(String tenant, String audience, boolean v2) {
        String base = v2
            ? "https://login.microsoftonline.com/" + tenant + "/v2.0"
            : "https://login.microsoftonline.com/" + tenant;
        return new ProviderConfig(
            base + "/.well-known/openid-configuration",
            null,
            base,
            audience,
            Arrays.asList("RS256"),
            5);
    }
}

package io.iaiso.identity;

import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Configures how OIDC claims become IAIso scopes. */
public final class ScopeMapping {
    public final List<String> directClaims;
    public final Map<String, List<String>> groupToScopes;
    public final List<String> alwaysGrant;

    public ScopeMapping(List<String> directClaims,
                        Map<String, List<String>> groupToScopes,
                        List<String> alwaysGrant) {
        this.directClaims = Collections.unmodifiableList(
            directClaims != null ? directClaims : Collections.emptyList());
        this.groupToScopes = Collections.unmodifiableMap(
            groupToScopes != null ? new HashMap<>(groupToScopes) : new HashMap<>());
        this.alwaysGrant = Collections.unmodifiableList(
            alwaysGrant != null ? alwaysGrant : Collections.emptyList());
    }

    public static ScopeMapping defaults() {
        return new ScopeMapping(null, null, null);
    }
}

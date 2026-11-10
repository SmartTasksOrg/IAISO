package io.iaiso.identity;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.Test;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.*;

public class IdentityTest {

    @Test
    public void deriveDirectClaimString() {
        JsonObject claims = JsonParser.parseString(
            "{\"scope\": \"tools.search tools.fetch\"}").getAsJsonObject();
        List<String> out = OidcVerifier.deriveScopes(claims, ScopeMapping.defaults());
        assertTrue(out.contains("tools.search"));
        assertTrue(out.contains("tools.fetch"));
    }

    @Test
    public void deriveDirectClaimArray() {
        JsonObject claims = JsonParser.parseString(
            "{\"scp\": [\"a.b\", \"c\"]}").getAsJsonObject();
        List<String> out = OidcVerifier.deriveScopes(claims, ScopeMapping.defaults());
        assertEquals(Arrays.asList("a.b", "c"), out);
    }

    @Test
    public void deriveGroupToScopes() {
        JsonObject claims = JsonParser.parseString(
            "{\"groups\": [\"engineers\"]}").getAsJsonObject();
        Map<String, List<String>> g = new HashMap<>();
        g.put("engineers", Arrays.asList("tools.search", "tools.fetch"));
        ScopeMapping mapping = new ScopeMapping(java.util.Collections.emptyList(), g, null);
        List<String> out = OidcVerifier.deriveScopes(claims, mapping);
        assertTrue(out.contains("tools.search"));
        assertTrue(out.contains("tools.fetch"));
    }

    @Test
    public void alwaysGrantAdded() {
        JsonObject claims = new JsonObject();
        ScopeMapping mapping = new ScopeMapping(
            java.util.Collections.emptyList(), null, Arrays.asList("base"));
        assertEquals(Arrays.asList("base"), OidcVerifier.deriveScopes(claims, mapping));
    }

    @Test
    public void presetsHaveExpectedEndpoints() {
        ProviderConfig okta = ProviderConfig.okta("acme.okta.com", "api");
        assertTrue(okta.discoveryUrl.contains("acme.okta.com"));

        ProviderConfig auth0 = ProviderConfig.auth0("acme.auth0.com", "api");
        assertTrue(auth0.issuer.endsWith("/"));

        ProviderConfig azureV2 = ProviderConfig.azureAd("tenant-id", "api", true);
        assertTrue(azureV2.discoveryUrl.contains("v2.0"));
    }

    @Test
    public void verifyFailsWhenJwksNotLoaded() {
        OidcVerifier v = new OidcVerifier(ProviderConfig.defaults());
        try {
            v.verify("a.b.c");
            fail("expected exception");
        } catch (IdentityException expected) {}
    }
}

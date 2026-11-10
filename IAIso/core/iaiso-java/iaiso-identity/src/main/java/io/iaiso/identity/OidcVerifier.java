package io.iaiso.identity;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.iaiso.consent.Issuer;
import io.iaiso.consent.Scope;

import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.RSAPublicKeySpec;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * IAIso OIDC identity verifier.
 *
 * <p>This module is HTTP-free. Caller fetches the JWKS bytes (using
 * {@code java.net.http.HttpClient} or any HTTP library) and passes them
 * to {@link #setJwksFromBytes(byte[])}. This keeps the SDK
 * dependency-light and lets users use whichever HTTP client they prefer.
 */
public final class OidcVerifier {

    /** A single key from a JWKS document. */
    public static final class Jwk {
        public final String kty;
        public final String kid;
        public final String alg;       // nullable
        public final String use;       // nullable
        public final String n;         // nullable (RSA modulus)
        public final String e;         // nullable (RSA exponent)

        public Jwk(String kty, String kid, String alg, String use, String n, String e) {
            this.kty = kty; this.kid = kid; this.alg = alg; this.use = use;
            this.n = n; this.e = e;
        }
    }

    public static final class Jwks {
        public final List<Jwk> keys;
        public Jwks(List<Jwk> keys) {
            this.keys = Collections.unmodifiableList(new ArrayList<>(keys));
        }
    }

    private final ProviderConfig cfg;
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    private Jwks jwks;

    public OidcVerifier(ProviderConfig cfg) {
        this.cfg = cfg;
    }

    /** Inject pre-fetched JWKS bytes into the verifier's cache. */
    public void setJwksFromBytes(byte[] body) {
        try {
            JsonObject root = JsonParser.parseString(
                new String(body, StandardCharsets.UTF_8)).getAsJsonObject();
            JsonArray keysArr = root.getAsJsonArray("keys");
            List<Jwk> keys = new ArrayList<>();
            for (JsonElement el : keysArr) {
                JsonObject k = el.getAsJsonObject();
                keys.add(new Jwk(
                    str(k, "kty"), str(k, "kid"), str(k, "alg"), str(k, "use"),
                    str(k, "n"), str(k, "e")));
            }
            lock.writeLock().lock();
            try {
                this.jwks = new Jwks(keys);
            } finally {
                lock.writeLock().unlock();
            }
        } catch (Exception e) {
            throw new IdentityException("JWKS parse failed: " + e.getMessage(), e);
        }
    }

    /**
     * Verify {@code token} against the cached JWKS and validate claims.
     * Returns the verified claims as a {@link JsonObject}.
     */
    public JsonObject verify(String token) {
        Jwks j;
        lock.readLock().lock();
        try { j = this.jwks; } finally { lock.readLock().unlock(); }
        if (j == null) {
            throw new IdentityException("oidc: JWKS not loaded; call setJwksFromBytes() first");
        }

        String[] parts = token.split("\\.");
        if (parts.length != 3) {
            throw new IdentityException("oidc: malformed JWT");
        }
        Base64.Decoder dec = Base64.getUrlDecoder();
        JsonObject header;
        JsonObject claims;
        byte[] signature;
        try {
            header = JsonParser.parseString(
                new String(dec.decode(parts[0]), StandardCharsets.UTF_8)).getAsJsonObject();
            claims = JsonParser.parseString(
                new String(dec.decode(parts[1]), StandardCharsets.UTF_8)).getAsJsonObject();
            signature = dec.decode(parts[2]);
        } catch (Exception e) {
            throw new IdentityException("oidc: malformed JWT", e);
        }

        String alg = header.has("alg") ? header.get("alg").getAsString() : "";
        if (!cfg.allowedAlgorithms.contains(alg)) {
            throw new IdentityException("oidc: algorithm not allowed: " + alg);
        }
        String kid = header.has("kid") ? header.get("kid").getAsString() : "";

        Jwk match = null;
        for (Jwk k : j.keys) {
            if (k.kid != null && k.kid.equals(kid)) { match = k; break; }
        }
        if (match == null && j.keys.size() == 1 && (kid == null || kid.isEmpty())) {
            match = j.keys.get(0);
        }
        if (match == null) {
            throw new IdentityException("oidc: kid " + kid + " not found in JWKS");
        }
        if (!"RSA".equals(match.kty)) {
            throw new IdentityException("oidc: unsupported key type: " + match.kty);
        }

        try {
            byte[] modulus = dec.decode(match.n);
            byte[] exponent = dec.decode(match.e);
            RSAPublicKeySpec spec = new RSAPublicKeySpec(
                new BigInteger(1, modulus), new BigInteger(1, exponent));
            PublicKey pub = KeyFactory.getInstance("RSA").generatePublic(spec);

            // Verify signature
            java.security.Signature sig = java.security.Signature.getInstance("SHA256withRSA");
            sig.initVerify(pub);
            sig.update((parts[0] + "." + parts[1]).getBytes(StandardCharsets.UTF_8));
            if (!sig.verify(signature)) {
                throw new IdentityException("oidc: signature verification failed");
            }
        } catch (IdentityException e) {
            throw e;
        } catch (Exception e) {
            throw new IdentityException("oidc: signature verification error: " + e.getMessage(), e);
        }

        // Issuer check
        if (cfg.issuer != null && !cfg.issuer.isEmpty()) {
            String iss = claims.has("iss") ? claims.get("iss").getAsString() : "";
            if (!cfg.issuer.equals(iss)) {
                throw new IdentityException(
                    "oidc: iss mismatch: got " + iss + ", want " + cfg.issuer);
            }
        }

        // Expiry check
        if (claims.has("exp")) {
            long exp = claims.get("exp").getAsLong();
            long now = System.currentTimeMillis() / 1000L;
            if (exp + cfg.leewaySeconds < now) {
                throw new IdentityException("oidc: token expired");
            }
        }

        // Audience check
        if (cfg.audience != null && !cfg.audience.isEmpty()) {
            if (!audienceMatches(claims.get("aud"), cfg.audience)) {
                throw new IdentityException(
                    "oidc: aud mismatch (expected " + cfg.audience + ")");
            }
        }
        return claims;
    }

    private static boolean audienceMatches(JsonElement aud, String want) {
        if (aud == null || aud.isJsonNull()) return false;
        if (aud.isJsonPrimitive()) return want.equals(aud.getAsString());
        if (aud.isJsonArray()) {
            for (JsonElement el : aud.getAsJsonArray()) {
                if (el.isJsonPrimitive() && want.equals(el.getAsString())) return true;
            }
        }
        return false;
    }

    private static String str(JsonObject o, String key) {
        return o.has(key) && !o.get(key).isJsonNull() ? o.get(key).getAsString() : null;
    }

    /**
     * Convert verified claims into a deduplicated list of IAIso scopes.
     */
    public static List<String> deriveScopes(JsonObject claims, ScopeMapping mapping) {
        List<String> directClaims = mapping.directClaims.isEmpty()
            ? Arrays.asList("scp", "scope", "permissions")
            : mapping.directClaims;

        Set<String> seen = new LinkedHashSet<>();
        for (String c : directClaims) {
            if (!claims.has(c)) continue;
            JsonElement el = claims.get(c);
            if (el.isJsonPrimitive() && el.getAsJsonPrimitive().isString()) {
                for (String tok : el.getAsString().split("[\\s,]+")) {
                    if (!tok.isEmpty()) seen.add(tok);
                }
            } else if (el.isJsonArray()) {
                for (JsonElement i : el.getAsJsonArray()) {
                    if (i.isJsonPrimitive()) seen.add(i.getAsString());
                }
            }
        }
        List<String> groups = new ArrayList<>();
        for (String c : new String[]{"groups", "roles"}) {
            if (claims.has(c) && claims.get(c).isJsonArray()) {
                for (JsonElement el : claims.getAsJsonArray(c)) {
                    if (el.isJsonPrimitive()) groups.add(el.getAsString());
                }
            }
        }
        for (String g : groups) {
            List<String> mapped = mapping.groupToScopes.get(g);
            if (mapped != null) seen.addAll(mapped);
        }
        seen.addAll(mapping.alwaysGrant);
        return new ArrayList<>(seen);
    }

    /** Mint an IAIso consent scope from a verified OIDC identity. */
    public static Scope issueFromOidc(OidcVerifier verifier, Issuer issuer,
                                      String token, ScopeMapping mapping,
                                      long ttlSeconds, String executionId) {
        JsonObject claims = verifier.verify(token);
        String subject = claims.has("sub") ? claims.get("sub").getAsString() : "unknown";
        List<String> scopes = deriveScopes(claims, mapping);

        JsonObject metadata = new JsonObject();
        if (claims.has("iss")) metadata.add("oidc_iss", claims.get("iss"));
        if (claims.has("jti")) metadata.add("oidc_jti", claims.get("jti"));
        if (claims.has("aud")) metadata.add("oidc_aud", claims.get("aud"));

        return issuer.issue(subject, scopes, executionId, ttlSeconds,
            metadata.size() > 0 ? metadata : null);
    }
}

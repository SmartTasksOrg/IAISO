package io.iaiso.consent;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.security.PrivateKey;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

/**
 * Mints signed consent tokens.
 *
 * <p>Use HS256 with a shared secret (the standard case) or RS256 with
 * a private key (for cross-service delegation).
 */
public final class Issuer {

    /** Supplier for the issuer's notion of "now" in seconds. */
    @FunctionalInterface
    public interface SecondsClock {
        long nowSeconds();
        static SecondsClock wallclock() {
            return () -> System.currentTimeMillis() / 1000L;
        }
    }

    private final byte[] hsKey;
    private final PrivateKey rsKey;
    private final Algorithm algorithm;
    private final String issuer;
    private final long defaultTtlSeconds;
    private final SecondsClock clock;
    private final SecureRandom rng = new SecureRandom();

    private Issuer(Builder b) {
        this.hsKey = b.hsKey;
        this.rsKey = b.rsKey;
        this.algorithm = b.algorithm;
        this.issuer = b.issuer;
        this.defaultTtlSeconds = b.defaultTtlSeconds;
        this.clock = b.clock != null ? b.clock : SecondsClock.wallclock();
    }

    public static Builder builder() {
        return new Builder();
    }

    /** Issue a token. */
    public Scope issue(String subject, List<String> scopes, String executionId,
                       Long ttlSeconds, JsonObject metadata) {
        long now = clock.nowSeconds();
        long ttl = ttlSeconds != null ? ttlSeconds : defaultTtlSeconds;
        long exp = now + ttl;
        String jti = generateJti();

        JsonObject claims = new JsonObject();
        claims.addProperty("iss", issuer);
        claims.addProperty("sub", subject);
        claims.addProperty("iat", now);
        claims.addProperty("exp", exp);
        claims.addProperty("jti", jti);
        JsonArray scopesArr = new JsonArray();
        for (String s : scopes) {
            scopesArr.add(s);
        }
        claims.add("scopes", scopesArr);
        if (executionId != null && !executionId.isEmpty()) {
            claims.addProperty("execution_id", executionId);
        }
        if (metadata != null && metadata.size() > 0) {
            claims.add("metadata", metadata);
        }

        String token = Jwt.sign(algorithm, claims, hsKey, rsKey);
        return new Scope(
            token, subject, new ArrayList<>(scopes),
            executionId, jti, now, exp,
            metadata != null ? metadata : new JsonObject());
    }

    /** Generate a 64-byte base64url-without-padding HS256 secret. */
    public static String generateHs256Secret() {
        byte[] buf = new byte[64];
        new SecureRandom().nextBytes(buf);
        return Jwt.b64url(buf);
    }

    private String generateJti() {
        byte[] buf = new byte[16];
        rng.nextBytes(buf);
        return HexFormat.of().formatHex(buf);
    }

    public static final class Builder {
        private byte[] hsKey;
        private PrivateKey rsKey;
        private Algorithm algorithm = Algorithm.HS256;
        private String issuer = "iaiso";
        private long defaultTtlSeconds = 3600;
        private SecondsClock clock;

        public Builder hsKey(byte[] v) { this.hsKey = v; return this; }
        public Builder rsKey(PrivateKey v) { this.rsKey = v; return this; }
        public Builder algorithm(Algorithm v) { this.algorithm = v; return this; }
        public Builder issuer(String v) { this.issuer = v; return this; }
        public Builder defaultTtlSeconds(long v) { this.defaultTtlSeconds = v; return this; }
        public Builder clock(SecondsClock v) { this.clock = v; return this; }

        public Issuer build() { return new Issuer(this); }
    }
}

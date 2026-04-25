package io.iaiso.consent;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.security.PublicKey;
import java.util.ArrayList;
import java.util.List;

/**
 * Verifies signed consent tokens.
 */
public final class Verifier {

    @FunctionalInterface
    public interface SecondsClock {
        long nowSeconds();
        static SecondsClock wallclock() {
            return () -> System.currentTimeMillis() / 1000L;
        }
    }

    private final byte[] hsKey;
    private final PublicKey rsKey;
    private final Algorithm algorithm;
    private final String issuer;
    private final RevocationList revocationList;   // nullable
    private final long leewaySeconds;
    private final SecondsClock clock;

    private Verifier(Builder b) {
        this.hsKey = b.hsKey;
        this.rsKey = b.rsKey;
        this.algorithm = b.algorithm;
        this.issuer = b.issuer;
        this.revocationList = b.revocationList;
        this.leewaySeconds = b.leewaySeconds;
        this.clock = b.clock != null ? b.clock : SecondsClock.wallclock();
    }

    public static Builder builder() { return new Builder(); }

    /**
     * Verify {@code token}. If {@code requestedExecutionId} is non-null
     * and the token is bound to a different execution, throws
     * {@link ConsentException.InvalidToken}.
     */
    public Scope verify(String token, String requestedExecutionId) {
        Jwt.Parsed parsed = Jwt.parse(token);

        // Algorithm check from header
        JsonElement algElem = parsed.header.get("alg");
        if (algElem == null || !algorithm.wireName().equals(algElem.getAsString())) {
            throw new ConsentException.InvalidToken(
                "unexpected algorithm: " + (algElem == null ? "missing" : algElem.getAsString()));
        }

        // Signature check
        if (!Jwt.verifySignature(parsed, algorithm, hsKey, rsKey)) {
            throw new ConsentException.InvalidToken("signature verification failed");
        }

        JsonObject claims = parsed.claims;

        // Required claims
        for (String required : new String[]{"exp", "iat", "iss", "sub", "jti"}) {
            if (!claims.has(required)) {
                throw new ConsentException.InvalidToken(
                    "missing required claim: " + required);
            }
        }

        // Issuer
        String issClaim = claims.get("iss").getAsString();
        if (!issuer.equals(issClaim)) {
            throw new ConsentException.InvalidToken(
                "iss mismatch: got " + issClaim + ", want " + issuer);
        }

        // Expiry
        long exp = claims.get("exp").getAsLong();
        long now = clock.nowSeconds();
        if (exp + leewaySeconds < now) {
            throw new ConsentException.ExpiredToken();
        }

        // Revocation
        String jti = claims.get("jti").getAsString();
        if (revocationList != null && revocationList.isRevoked(jti)) {
            throw new ConsentException.RevokedToken(jti);
        }

        // Execution binding
        String tokenExec = claims.has("execution_id")
            ? claims.get("execution_id").getAsString()
            : null;
        if (requestedExecutionId != null && tokenExec != null
                && !requestedExecutionId.equals(tokenExec)) {
            throw new ConsentException.InvalidToken(
                "token bound to " + tokenExec + ", requested " + requestedExecutionId);
        }

        // Build scope
        String subject = claims.get("sub").getAsString();
        long iat = claims.get("iat").getAsLong();
        List<String> scopes = new ArrayList<>();
        if (claims.has("scopes") && claims.get("scopes").isJsonArray()) {
            JsonArray arr = claims.getAsJsonArray("scopes");
            for (JsonElement e : arr) {
                scopes.add(e.getAsString());
            }
        }
        JsonObject metadata = claims.has("metadata") && claims.get("metadata").isJsonObject()
            ? claims.getAsJsonObject("metadata")
            : new JsonObject();

        return new Scope(token, subject, scopes, tokenExec, jti, iat, exp, metadata);
    }

    public static final class Builder {
        private byte[] hsKey;
        private PublicKey rsKey;
        private Algorithm algorithm = Algorithm.HS256;
        private String issuer = "iaiso";
        private RevocationList revocationList;
        private long leewaySeconds = 5;
        private SecondsClock clock;

        public Builder hsKey(byte[] v) { this.hsKey = v; return this; }
        public Builder rsKey(PublicKey v) { this.rsKey = v; return this; }
        public Builder algorithm(Algorithm v) { this.algorithm = v; return this; }
        public Builder issuer(String v) { this.issuer = v; return this; }
        public Builder revocationList(RevocationList v) { this.revocationList = v; return this; }
        public Builder leewaySeconds(long v) { this.leewaySeconds = v; return this; }
        public Builder clock(SecondsClock v) { this.clock = v; return this; }

        public Verifier build() { return new Verifier(this); }
    }
}

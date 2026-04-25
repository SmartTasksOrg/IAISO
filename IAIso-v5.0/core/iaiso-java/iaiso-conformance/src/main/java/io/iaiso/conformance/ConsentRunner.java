package io.iaiso.conformance;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.iaiso.consent.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

final class ConsentRunner {
    private ConsentRunner() {}

    static List<VectorResult> run(Path specRoot) throws IOException {
        Path file = specRoot.resolve("consent").resolve("vectors.json");
        JsonObject doc = JsonParser.parseString(
            new String(Files.readAllBytes(file))).getAsJsonObject();
        String sharedKey = doc.get("hs256_key_shared").getAsString();

        List<VectorResult> out = new ArrayList<>();
        if (doc.has("scope_match")) {
            for (JsonElement el : doc.getAsJsonArray("scope_match")) {
                out.add(runScopeMatch(el.getAsJsonObject()));
            }
        }
        if (doc.has("scope_match_errors")) {
            for (JsonElement el : doc.getAsJsonArray("scope_match_errors")) {
                out.add(runScopeMatchError(el.getAsJsonObject()));
            }
        }
        if (doc.has("valid_tokens")) {
            for (JsonElement el : doc.getAsJsonArray("valid_tokens")) {
                out.add(runValidToken(sharedKey, el.getAsJsonObject()));
            }
        }
        if (doc.has("invalid_tokens")) {
            for (JsonElement el : doc.getAsJsonArray("invalid_tokens")) {
                out.add(runInvalidToken(sharedKey, el.getAsJsonObject()));
            }
        }
        if (doc.has("issue_and_verify_roundtrip")) {
            for (JsonElement el : doc.getAsJsonArray("issue_and_verify_roundtrip")) {
                out.add(runRoundtrip(sharedKey, el.getAsJsonObject()));
            }
        }
        return out;
    }

    private static VectorResult runScopeMatch(JsonObject v) {
        String name = "scope_match/" + v.get("name").getAsString();
        List<String> granted = new ArrayList<>();
        for (JsonElement g : v.getAsJsonArray("granted")) granted.add(g.getAsString());
        String requested = v.get("requested").getAsString();
        boolean expected = v.get("expected").getAsBoolean();
        try {
            boolean got = Scopes.granted(granted, requested);
            if (got != expected) {
                return VectorResult.fail("consent", name, "got " + got + ", want " + expected);
            }
            return VectorResult.pass("consent", name);
        } catch (RuntimeException e) {
            return VectorResult.fail("consent", name, "unexpected exception: " + e.getMessage());
        }
    }

    private static VectorResult runScopeMatchError(JsonObject v) {
        String name = "scope_match_errors/" + v.get("name").getAsString();
        List<String> granted = new ArrayList<>();
        for (JsonElement g : v.getAsJsonArray("granted")) granted.add(g.getAsString());
        String requested = v.get("requested").getAsString();
        String expectErr = v.get("expect_error").getAsString();
        try {
            Scopes.granted(granted, requested);
            return VectorResult.fail("consent", name,
                "expected error containing '" + expectErr + "', got Ok");
        } catch (IllegalArgumentException e) {
            String msg = e.getMessage().toLowerCase();
            if (!msg.contains(expectErr.toLowerCase())) {
                return VectorResult.fail("consent", name,
                    "expected error containing '" + expectErr + "', got: " + e.getMessage());
            }
            return VectorResult.pass("consent", name);
        }
    }

    private static Algorithm parseAlg(JsonObject v) {
        if (v.has("algorithm")) {
            try { return Algorithm.fromWire(v.get("algorithm").getAsString()); }
            catch (Exception ignored) {}
        }
        return Algorithm.HS256;
    }

    private static String stringOrDefault(JsonObject v, String key, String dflt) {
        if (v.has(key) && !v.get(key).isJsonNull()) return v.get(key).getAsString();
        return dflt;
    }

    private static VectorResult runValidToken(String sharedKey, JsonObject v) {
        String name = "valid_tokens/" + v.get("name").getAsString();
        long now = v.get("now").getAsLong();
        String issuer = stringOrDefault(v, "issuer", "iaiso");
        Algorithm alg = parseAlg(v);
        String token = v.get("token").getAsString();
        JsonObject expected = v.getAsJsonObject("expected");

        Verifier verifier = Verifier.builder()
            .hsKey(sharedKey.getBytes())
            .algorithm(alg)
            .issuer(issuer)
            .clock(() -> now)
            .build();
        try {
            Scope s = verifier.verify(token, null);
            if (!s.getSubject().equals(expected.get("sub").getAsString())) {
                return VectorResult.fail("consent", name,
                    "sub: got " + s.getSubject() + ", want " + expected.get("sub"));
            }
            if (!s.getJti().equals(expected.get("jti").getAsString())) {
                return VectorResult.fail("consent", name,
                    "jti: got " + s.getJti() + ", want " + expected.get("jti"));
            }
            List<String> wantScopes = new ArrayList<>();
            for (JsonElement el : expected.getAsJsonArray("scopes")) wantScopes.add(el.getAsString());
            if (!s.getScopes().equals(wantScopes)) {
                return VectorResult.fail("consent", name, "scopes mismatch");
            }
            // execution_id may be null
            String wantExec = expected.has("execution_id") && !expected.get("execution_id").isJsonNull()
                ? expected.get("execution_id").getAsString() : null;
            if (wantExec == null ? s.getExecutionId() != null : !wantExec.equals(s.getExecutionId())) {
                return VectorResult.fail("consent", name,
                    "execution_id: got " + s.getExecutionId() + ", want " + wantExec);
            }
            return VectorResult.pass("consent", name);
        } catch (RuntimeException e) {
            return VectorResult.fail("consent", name, "verify failed: " + e.getMessage());
        }
    }

    private static VectorResult runInvalidToken(String sharedKey, JsonObject v) {
        String name = "invalid_tokens/" + v.get("name").getAsString();
        long now = v.get("now").getAsLong();
        String issuer = stringOrDefault(v, "issuer", "iaiso");
        Algorithm alg = parseAlg(v);
        String token = v.get("token").getAsString();
        String execId = stringOrDefault(v, "execution_id", null);
        String expectErr = v.get("expect_error").getAsString();

        Verifier verifier = Verifier.builder()
            .hsKey(sharedKey.getBytes())
            .algorithm(alg)
            .issuer(issuer)
            .clock(() -> now)
            .build();
        try {
            verifier.verify(token, execId);
            return VectorResult.fail("consent", name,
                "expected error '" + expectErr + "', got Ok");
        } catch (ConsentException.ExpiredToken e) {
            if (!"expired".equals(expectErr)) {
                return VectorResult.fail("consent", name,
                    "expected '" + expectErr + "', got expired");
            }
            return VectorResult.pass("consent", name);
        } catch (ConsentException.RevokedToken e) {
            if (!"revoked".equals(expectErr)) {
                return VectorResult.fail("consent", name,
                    "expected '" + expectErr + "', got revoked");
            }
            return VectorResult.pass("consent", name);
        } catch (ConsentException.InvalidToken e) {
            if (!"invalid".equals(expectErr)) {
                return VectorResult.fail("consent", name,
                    "expected '" + expectErr + "', got invalid: " + e.getMessage());
            }
            return VectorResult.pass("consent", name);
        } catch (RuntimeException e) {
            return VectorResult.fail("consent", name,
                "unexpected exception type: " + e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }

    private static VectorResult runRoundtrip(String sharedKey, JsonObject v) {
        String name = "roundtrip/" + v.get("name").getAsString();
        JsonObject issueSpec = v.getAsJsonObject("issue");
        long ttl = issueSpec.has("ttl_seconds") ? issueSpec.get("ttl_seconds").getAsLong() : 3600;
        String subject = issueSpec.get("subject").getAsString();
        List<String> scopes = new ArrayList<>();
        for (JsonElement el : issueSpec.getAsJsonArray("scopes")) scopes.add(el.getAsString());
        String execId = stringOrDefault(issueSpec, "execution_id", null);
        JsonObject metadata = issueSpec.has("metadata") && issueSpec.get("metadata").isJsonObject()
            ? issueSpec.getAsJsonObject("metadata") : null;

        long now = v.has("now") && !v.get("now").isJsonNull()
            ? v.get("now").getAsLong() : 1_700_000_000L;
        String issuer = stringOrDefault(v, "issuer", "iaiso");
        Algorithm alg = parseAlg(v);

        Issuer is = Issuer.builder()
            .hsKey(sharedKey.getBytes())
            .algorithm(alg)
            .issuer(issuer)
            .clock(() -> now)
            .build();
        Scope scope;
        try {
            scope = is.issue(subject, scopes, execId, ttl, metadata);
        } catch (RuntimeException e) {
            return VectorResult.fail("consent", name, "issue failed: " + e.getMessage());
        }

        boolean expectSuccess = v.has("expected_after_verify_succeeds")
            && v.get("expected_after_verify_succeeds").getAsBoolean();
        String verifyExec = stringOrDefault(v, "verify_with_execution_id", null);

        Verifier ver = Verifier.builder()
            .hsKey(sharedKey.getBytes())
            .algorithm(alg)
            .issuer(issuer)
            .clock(() -> now + 1)
            .build();
        try {
            Scope verified = ver.verify(scope.getToken(), verifyExec);
            if (!expectSuccess) {
                return VectorResult.fail("consent", name, "expected verify to fail, succeeded");
            }
            if (!verified.getSubject().equals(subject)) {
                return VectorResult.fail("consent", name, "subject mismatch");
            }
            if (!verified.getScopes().equals(scopes)) {
                return VectorResult.fail("consent", name, "scopes mismatch");
            }
            return VectorResult.pass("consent", name);
        } catch (RuntimeException e) {
            if (expectSuccess) {
                return VectorResult.fail("consent", name,
                    "expected verify to succeed, failed: " + e.getMessage());
            }
            return VectorResult.pass("consent", name);
        }
    }
}

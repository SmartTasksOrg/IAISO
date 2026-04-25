package io.iaiso.consent;

import org.junit.Test;

import java.util.Arrays;
import java.util.List;

import static org.junit.Assert.*;

public class ConsentTest {

    private static final byte[] SECRET =
        "test_secret_long_enough_for_hs256_security_xx".getBytes();

    @Test
    public void scopeExactMatch() {
        assertTrue(Scopes.granted(Arrays.asList("tools.search"), "tools.search"));
    }

    @Test
    public void scopePrefixAtBoundary() {
        assertTrue(Scopes.granted(Arrays.asList("tools"), "tools.search"));
    }

    @Test
    public void scopeSubstringNotBoundary() {
        assertFalse(Scopes.granted(Arrays.asList("tools"), "toolsbar"));
    }

    @Test
    public void scopeMoreSpecificDoesntSatisfyLessSpecific() {
        assertFalse(Scopes.granted(Arrays.asList("tools.search.bulk"), "tools.search"));
    }

    @Test
    public void scopeEmptyRequestedThrows() {
        try {
            Scopes.granted(Arrays.asList("tools"), "");
            fail("expected IllegalArgumentException");
        } catch (IllegalArgumentException expected) {}
    }

    @Test
    public void issueVerifyRoundtrip() {
        Issuer issuer = Issuer.builder()
            .hsKey(SECRET)
            .algorithm(Algorithm.HS256)
            .issuer("iaiso")
            .clock(() -> 1_700_000_000L)
            .build();
        Scope scope = issuer.issue("user-1",
            Arrays.asList("tools.search", "tools.fetch"),
            null, 3600L, null);
        assertNotNull(scope.getToken());

        Verifier verifier = Verifier.builder()
            .hsKey(SECRET)
            .algorithm(Algorithm.HS256)
            .issuer("iaiso")
            .clock(() -> 1_700_000_001L)
            .build();
        Scope verified = verifier.verify(scope.getToken(), null);
        assertEquals("user-1", verified.getSubject());
        assertTrue(verified.grants("tools.search"));
    }

    @Test
    public void verifyRejectsExpired() {
        Issuer issuer = Issuer.builder()
            .hsKey(SECRET)
            .clock(() -> 1_700_000_000L)
            .build();
        Scope scope = issuer.issue("u", Arrays.asList("tools"), null, 1L, null);

        Verifier verifier = Verifier.builder()
            .hsKey(SECRET)
            .clock(() -> 1_700_000_010L)  // 10s past exp
            .build();
        try {
            verifier.verify(scope.getToken(), null);
            fail("expected ExpiredToken");
        } catch (ConsentException.ExpiredToken expected) {}
    }

    @Test
    public void verifyHonorsRevocation() {
        Issuer issuer = Issuer.builder()
            .hsKey(SECRET)
            .clock(() -> 1_700_000_000L)
            .build();
        Scope scope = issuer.issue("u", Arrays.asList("tools"), null, 3600L, null);
        RevocationList rl = new RevocationList();
        rl.revoke(scope.getJti());

        Verifier verifier = Verifier.builder()
            .hsKey(SECRET)
            .revocationList(rl)
            .clock(() -> 1_700_000_001L)
            .build();
        try {
            verifier.verify(scope.getToken(), null);
            fail("expected RevokedToken");
        } catch (ConsentException.RevokedToken expected) {
            assertEquals(scope.getJti(), expected.getJti());
        }
    }

    @Test
    public void verifyHonorsExecutionBinding() {
        Issuer issuer = Issuer.builder()
            .hsKey(SECRET)
            .clock(() -> 1_700_000_000L)
            .build();
        Scope scope = issuer.issue("u", Arrays.asList("tools"),
            "exec-abc", 3600L, null);

        Verifier verifier = Verifier.builder()
            .hsKey(SECRET)
            .clock(() -> 1_700_000_001L)
            .build();
        try {
            verifier.verify(scope.getToken(), "exec-xyz");
            fail("expected InvalidToken for binding mismatch");
        } catch (ConsentException.InvalidToken expected) {}
    }

    @Test
    public void verifyRejectsTamperedToken() {
        Issuer issuer = Issuer.builder()
            .hsKey(SECRET)
            .clock(() -> 1_700_000_000L)
            .build();
        Scope scope = issuer.issue("u", Arrays.asList("tools"), null, 3600L, null);
        // Flip a character in the signature part
        String tampered = scope.getToken().substring(0, scope.getToken().length() - 5) + "XXXXX";

        Verifier verifier = Verifier.builder()
            .hsKey(SECRET)
            .clock(() -> 1_700_000_001L)
            .build();
        try {
            verifier.verify(tampered, null);
            fail("expected InvalidToken");
        } catch (ConsentException.InvalidToken expected) {}
    }

    @Test
    public void generateHs256SecretIsLongEnough() {
        String s = Issuer.generateHs256Secret();
        assertTrue("generated secret too short: " + s.length(), s.length() >= 64);
    }
}

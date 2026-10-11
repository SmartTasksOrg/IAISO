package consent

import (
	"errors"
	"testing"
)

const testKey = "test_secret_do_not_use_in_production_this_is_for_conformance_vectors_only_deadbeef"

func TestScopeGrantingAtSegmentBoundaries(t *testing.T) {
	cases := []struct {
		granted   []string
		requested string
		want      bool
	}{
		{[]string{"tools.search"}, "tools.search", true},
		{[]string{"tools"}, "tools.search", true},
		{[]string{"tools"}, "tools.a.b.c.d", true},
		{[]string{"tools.search.bulk"}, "tools.search", false},
		{[]string{"tool"}, "tools.search", false},
		{[]string{"tools"}, "toolsbar", false}, // substring, not a boundary
		{[]string{"Tools"}, "tools", false},    // case-sensitive
		{[]string{}, "tools.search", false},
		{[]string{"billing", "tools"}, "tools.search", true},
	}
	for _, tc := range cases {
		got, err := ScopeGranted(tc.granted, tc.requested)
		if err != nil {
			t.Fatalf("%v/%q: %v", tc.granted, tc.requested, err)
		}
		if got != tc.want {
			t.Errorf("%v grants %q = %v, want %v", tc.granted, tc.requested, got, tc.want)
		}
	}
}

func TestEmptyRequestedScopeIsAnErrorNotADenial(t *testing.T) {
	if _, err := ScopeGranted([]string{"tools"}, ""); !errors.Is(err, ErrEmptyRequestedScope) {
		t.Fatalf("want ErrEmptyRequestedScope, got %v", err)
	}
}

func issuerAt(t *testing.T, now int64, alg Algorithm, key []byte) *Issuer {
	t.Helper()
	i, err := NewIssuer(IssuerOptions{SigningKey: key, Algorithm: alg, Clock: FixedClock(now)})
	if err != nil {
		t.Fatal(err)
	}
	return i
}

func verifierAt(t *testing.T, now int64, alg Algorithm, key []byte) *Verifier {
	t.Helper()
	v, err := NewVerifier(VerifierOptions{VerificationKey: key, Algorithm: alg, Clock: FixedClock(now)})
	if err != nil {
		t.Fatal(err)
	}
	return v
}

func TestHS256Roundtrip(t *testing.T) {
	const now = 1_700_000_000
	iss := issuerAt(t, now, HS256, []byte(testKey))
	scope, err := iss.Issue(IssueParams{Subject: "user-42", Scopes: []string{"tools.search"}, TTLSeconds: 60})
	if err != nil {
		t.Fatal(err)
	}
	got, err := verifierAt(t, now, HS256, []byte(testKey)).Verify(scope.Token, "")
	if err != nil {
		t.Fatal(err)
	}
	if got.Subject != "user-42" || !got.Grants("tools.search") {
		t.Fatalf("bad roundtrip: %+v", got)
	}
}

func TestExpiryUsesTheInjectedClock(t *testing.T) {
	iss := issuerAt(t, 1_700_000_000, HS256, []byte(testKey))
	scope, _ := iss.Issue(IssueParams{Subject: "u", Scopes: []string{"a"}, TTLSeconds: 60})
	// 61s later, plus 5s default leeway, still inside. 100s later, expired.
	if _, err := verifierAt(t, 1_700_000_063, HS256, []byte(testKey)).Verify(scope.Token, ""); err != nil {
		t.Fatalf("token expired inside leeway: %v", err)
	}
	_, err := verifierAt(t, 1_700_000_100, HS256, []byte(testKey)).Verify(scope.Token, "")
	if !errors.Is(err, ErrExpiredToken) {
		t.Fatalf("want ErrExpiredToken, got %v", err)
	}
}

func TestWrongKeyIsInvalid(t *testing.T) {
	iss := issuerAt(t, 1_700_000_000, HS256, []byte(testKey))
	scope, _ := iss.Issue(IssueParams{Subject: "u", Scopes: []string{"a"}, TTLSeconds: 60})
	_, err := verifierAt(t, 1_700_000_000, HS256, []byte("a-different-secret")).Verify(scope.Token, "")
	if !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("want ErrInvalidToken, got %v", err)
	}
}

func TestExecutionBindingMismatchIsInvalid(t *testing.T) {
	iss := issuerAt(t, 1_700_000_000, HS256, []byte(testKey))
	scope, _ := iss.Issue(IssueParams{
		Subject: "u", Scopes: []string{"a"}, TTLSeconds: 60, ExecutionID: "exec-abc",
	})
	v := verifierAt(t, 1_700_000_000, HS256, []byte(testKey))
	if _, err := v.Verify(scope.Token, "exec-abc"); err != nil {
		t.Fatalf("matching binding rejected: %v", err)
	}
	if _, err := v.Verify(scope.Token, "exec-xyz"); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("want ErrInvalidToken, got %v", err)
	}
}

func TestRevocation(t *testing.T) {
	const now = 1_700_000_000
	iss := issuerAt(t, now, HS256, []byte(testKey))
	scope, _ := iss.Issue(IssueParams{Subject: "u", Scopes: []string{"a"}, TTLSeconds: 60})
	rl := NewRevocationList()
	rl.Revoke(scope.JTI)
	v, err := NewVerifier(VerifierOptions{
		VerificationKey: []byte(testKey), Clock: FixedClock(now), RevocationList: rl,
	})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := v.Verify(scope.Token, ""); !errors.Is(err, ErrRevokedToken) {
		t.Fatalf("want ErrRevokedToken, got %v", err)
	}
}

func TestRS256Roundtrip(t *testing.T) {
	priv, pub := testRSAKeyPair(t)
	const now = 1_700_000_000
	iss, err := NewIssuer(IssuerOptions{SigningKey: priv, Algorithm: RS256, Clock: FixedClock(now)})
	if err != nil {
		t.Fatal(err)
	}
	scope, err := iss.Issue(IssueParams{Subject: "u", Scopes: []string{"tools.admin"}, TTLSeconds: 60})
	if err != nil {
		t.Fatal(err)
	}
	// The verifier holds only the public key: a compromised verifier host
	// cannot forge tokens. That is the whole point of RS256 here.
	v, err := NewVerifier(VerifierOptions{VerificationKey: pub, Algorithm: RS256, Clock: FixedClock(now)})
	if err != nil {
		t.Fatal(err)
	}
	got, err := v.Verify(scope.Token, "")
	if err != nil {
		t.Fatal(err)
	}
	if !got.Grants("tools.admin") {
		t.Fatal("RS256 token did not carry its scopes")
	}
}

func TestAlgorithmConfusionIsRejected(t *testing.T) {
	// A token signed HS256 must not verify against an RS256 verifier.
	iss := issuerAt(t, 1_700_000_000, HS256, []byte(testKey))
	scope, _ := iss.Issue(IssueParams{Subject: "u", Scopes: []string{"a"}, TTLSeconds: 60})
	_, pub := testRSAKeyPair(t)
	v, err := NewVerifier(VerifierOptions{
		VerificationKey: pub, Algorithm: RS256, Clock: FixedClock(1_700_000_000),
	})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := v.Verify(scope.Token, ""); err == nil {
		t.Fatal("RS256 verifier accepted an HS256 token")
	}
}

func TestStrictModeRefusesAutoGeneratedHS256Key(t *testing.T) {
	secret, err := GenerateHS256Secret()
	if err != nil {
		t.Fatal(err)
	}
	_, err = NewIssuer(IssuerOptions{
		SigningKey: []byte(secret), Algorithm: HS256,
		KeyAutoGenerated: true, EnforcementMode: "strict",
	})
	if err == nil {
		t.Fatal("strict mode accepted an auto-generated HS256 signing key")
	}
}

func TestValidScopeString(t *testing.T) {
	for _, s := range []string{"tools", "tools.search", "api-v2.user_read", "a.b.c"} {
		if !ValidScopeString(s) {
			t.Errorf("%q should be valid", s)
		}
	}
	for _, s := range []string{"", "Tools", "a..b", "a.", ".a", "tools/search"} {
		if ValidScopeString(s) {
			t.Errorf("%q should be invalid", s)
		}
	}
}

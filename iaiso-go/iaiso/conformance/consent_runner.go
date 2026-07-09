package conformance

import (
	"encoding/json"
	"errors"
	"strings"

	"github.com/iaiso/iaiso-go/iaiso/consent"
)

type scopeMatchVector struct {
	Name      string   `json:"name"`
	Granted   []string `json:"granted"`
	Requested string   `json:"requested"`
	Expected  bool     `json:"expected"`
}

type scopeMatchErrorVector struct {
	Name        string   `json:"name"`
	Granted     []string `json:"granted"`
	Requested   string   `json:"requested"`
	ExpectError string   `json:"expect_error"`
}

type validTokenExpected struct {
	Sub         string         `json:"sub"`
	JTI         string         `json:"jti"`
	Scopes      []string       `json:"scopes"`
	ExecutionID *string        `json:"execution_id"`
	Metadata    map[string]any `json:"metadata"`
}

type validTokenVector struct {
	Name        string             `json:"name"`
	Token       string             `json:"token"`
	Algorithm   string             `json:"algorithm"`
	Issuer      string             `json:"issuer"`
	Now         int64              `json:"now"`
	ExecutionID *string            `json:"execution_id"`
	Expected    validTokenExpected `json:"expected"`
}

type invalidTokenVector struct {
	Name        string  `json:"name"`
	Token       string  `json:"token"`
	Algorithm   string  `json:"algorithm"`
	Issuer      string  `json:"issuer"`
	Now         int64   `json:"now"`
	ExecutionID *string `json:"execution_id"`
	ExpectError string  `json:"expect_error"`
}

type roundtripIssue struct {
	Subject     string         `json:"subject"`
	Scopes      []string       `json:"scopes"`
	TTLSeconds  int64          `json:"ttl_seconds"`
	ExecutionID *string        `json:"execution_id"`
	Metadata    map[string]any `json:"metadata"`
}

type roundtripExpected struct {
	Subject     string   `json:"subject"`
	Scopes      []string `json:"scopes"`
	ExecutionID *string  `json:"execution_id"`
}

type roundtripVector struct {
	Name                  string            `json:"name"`
	Issue                 roundtripIssue    `json:"issue"`
	VerifyWithExecutionID *string           `json:"verify_with_execution_id"`
	Algorithm             string            `json:"algorithm"`
	Issuer                string            `json:"issuer"`
	Now                   *int64            `json:"now"`
	ExpectedAfterIssue    roundtripExpected `json:"expected_after_issue"`
	ExpectVerifySucceeds  bool              `json:"expected_after_verify_succeeds"`
}

type consentFile struct {
	HS256KeyShared          string                  `json:"hs256_key_shared"`
	ScopeMatch              []scopeMatchVector      `json:"scope_match"`
	ScopeMatchErrors        []scopeMatchErrorVector `json:"scope_match_errors"`
	ValidTokens             []validTokenVector      `json:"valid_tokens"`
	InvalidTokens           []invalidTokenVector    `json:"invalid_tokens"`
	IssueAndVerifyRoundtrip []roundtripVector       `json:"issue_and_verify_roundtrip"`
}

const defaultConsentNow int64 = 1_700_000_000

func runConsent(specRoot string) ([]Result, error) {
	raw, err := readVectors(specRoot, "consent")
	if err != nil {
		return nil, err
	}
	var file consentFile
	if err := json.Unmarshal(raw, &file); err != nil {
		return nil, err
	}
	key := []byte(file.HS256KeyShared)

	var out []Result
	for _, v := range file.ScopeMatch {
		out = append(out, runScopeMatch(v))
	}
	for _, v := range file.ScopeMatchErrors {
		out = append(out, runScopeMatchError(v))
	}
	for _, v := range file.ValidTokens {
		out = append(out, runValidToken(v, key))
	}
	for _, v := range file.InvalidTokens {
		out = append(out, runInvalidToken(v, key))
	}
	for _, v := range file.IssueAndVerifyRoundtrip {
		out = append(out, runRoundtrip(v, key))
	}
	return out, nil
}

func runScopeMatch(v scopeMatchVector) Result {
	const section = "consent"
	name := "scope_match/" + v.Name
	got, err := consent.ScopeGranted(v.Granted, v.Requested)
	if err != nil {
		return fail(section, name, "unexpected error: %v", err)
	}
	if got != v.Expected {
		return fail(section, name, "got %v, want %v", got, v.Expected)
	}
	return pass(section, name)
}

func runScopeMatchError(v scopeMatchErrorVector) Result {
	const section = "consent"
	name := "scope_match_errors/" + v.Name
	_, err := consent.ScopeGranted(v.Granted, v.Requested)
	if err == nil {
		return fail(section, name, "expected error containing %q, got nil", v.ExpectError)
	}
	if !strings.Contains(err.Error(), v.ExpectError) {
		return fail(section, name, "expected error containing %q, got %q", v.ExpectError, err.Error())
	}
	return pass(section, name)
}

func verifierFor(alg, issuer string, now int64, key []byte) (*consent.Verifier, error) {
	if alg == "" {
		alg = "HS256"
	}
	if issuer == "" {
		issuer = "iaiso"
	}
	return consent.NewVerifier(consent.VerifierOptions{
		VerificationKey: key,
		Algorithm:       consent.Algorithm(alg),
		Issuer:          issuer,
		Clock:           consent.FixedClock(now),
	})
}

func runValidToken(v validTokenVector, key []byte) Result {
	const section = "consent"
	name := "valid_tokens/" + v.Name

	verifier, err := verifierFor(v.Algorithm, v.Issuer, v.Now, key)
	if err != nil {
		return fail(section, name, "verifier construction failed: %v", err)
	}
	execID := ""
	if v.ExecutionID != nil {
		execID = *v.ExecutionID
	}
	scope, err := verifier.Verify(v.Token, execID)
	if err != nil {
		return fail(section, name, "verification failed: %v", err)
	}
	if scope.Subject != v.Expected.Sub {
		return fail(section, name, "sub: got %q, want %q", scope.Subject, v.Expected.Sub)
	}
	if scope.JTI != v.Expected.JTI {
		return fail(section, name, "jti: got %q, want %q", scope.JTI, v.Expected.JTI)
	}
	if !equalStrings(scope.Scopes, v.Expected.Scopes) {
		return fail(section, name, "scopes: got %v, want %v", scope.Scopes, v.Expected.Scopes)
	}
	wantExec := ""
	if v.Expected.ExecutionID != nil {
		wantExec = *v.Expected.ExecutionID
	}
	if scope.ExecutionID != wantExec {
		return fail(section, name, "execution_id: got %q, want %q", scope.ExecutionID, wantExec)
	}
	if len(scope.Metadata) != len(v.Expected.Metadata) {
		return fail(section, name, "metadata size: got %d, want %d",
			len(scope.Metadata), len(v.Expected.Metadata))
	}
	return pass(section, name)
}

func runInvalidToken(v invalidTokenVector, key []byte) Result {
	const section = "consent"
	name := "invalid_tokens/" + v.Name

	verifier, err := verifierFor(v.Algorithm, v.Issuer, v.Now, key)
	if err != nil {
		return fail(section, name, "verifier construction failed: %v", err)
	}
	execID := ""
	if v.ExecutionID != nil {
		execID = *v.ExecutionID
	}
	_, err = verifier.Verify(v.Token, execID)
	if err == nil {
		return fail(section, name, "expected error containing %q, got nil", v.ExpectError)
	}
	if !matchesExpectedConsentError(err, v.ExpectError) {
		return fail(section, name, "expected error containing %q, got %q", v.ExpectError, err.Error())
	}
	return pass(section, name)
}

// matchesExpectedConsentError maps the vectors' error keywords ("expired",
// "invalid", "revoked") onto sentinel errors, falling back to substring.
func matchesExpectedConsentError(err error, expect string) bool {
	switch strings.ToLower(expect) {
	case "expired":
		return errors.Is(err, consent.ErrExpiredToken)
	case "invalid":
		return errors.Is(err, consent.ErrInvalidToken)
	case "revoked":
		return errors.Is(err, consent.ErrRevokedToken)
	}
	return strings.Contains(strings.ToLower(err.Error()), strings.ToLower(expect))
}

func runRoundtrip(v roundtripVector, key []byte) Result {
	const section = "consent"
	name := "issue_and_verify_roundtrip/" + v.Name

	now := defaultConsentNow
	if v.Now != nil {
		now = *v.Now
	}
	alg := v.Algorithm
	if alg == "" {
		alg = "HS256"
	}
	issuerName := v.Issuer
	if issuerName == "" {
		issuerName = "iaiso"
	}

	issuer, err := consent.NewIssuer(consent.IssuerOptions{
		SigningKey: key,
		Algorithm:  consent.Algorithm(alg),
		Issuer:     issuerName,
		Clock:      consent.FixedClock(now),
	})
	if err != nil {
		return fail(section, name, "issuer construction failed: %v", err)
	}

	execID := ""
	if v.Issue.ExecutionID != nil {
		execID = *v.Issue.ExecutionID
	}
	issued, err := issuer.Issue(consent.IssueParams{
		Subject:     v.Issue.Subject,
		Scopes:      v.Issue.Scopes,
		ExecutionID: execID,
		TTLSeconds:  v.Issue.TTLSeconds,
		Metadata:    v.Issue.Metadata,
	})
	if err != nil {
		return fail(section, name, "issue failed: %v", err)
	}
	if issued.Subject != v.ExpectedAfterIssue.Subject {
		return fail(section, name, "issued subject: got %q, want %q",
			issued.Subject, v.ExpectedAfterIssue.Subject)
	}
	if !equalStrings(issued.Scopes, v.ExpectedAfterIssue.Scopes) {
		return fail(section, name, "issued scopes: got %v, want %v",
			issued.Scopes, v.ExpectedAfterIssue.Scopes)
	}
	wantExec := ""
	if v.ExpectedAfterIssue.ExecutionID != nil {
		wantExec = *v.ExpectedAfterIssue.ExecutionID
	}
	if issued.ExecutionID != wantExec {
		return fail(section, name, "issued execution_id: got %q, want %q",
			issued.ExecutionID, wantExec)
	}

	verifier, err := verifierFor(alg, issuerName, now, key)
	if err != nil {
		return fail(section, name, "verifier construction failed: %v", err)
	}
	verifyExec := ""
	if v.VerifyWithExecutionID != nil {
		verifyExec = *v.VerifyWithExecutionID
	}
	verified, err := verifier.Verify(issued.Token, verifyExec)
	if v.ExpectVerifySucceeds {
		if err != nil {
			return fail(section, name, "roundtrip verification failed: %v", err)
		}
		if verified.Subject != issued.Subject || verified.JTI != issued.JTI {
			return fail(section, name, "roundtrip claims mismatch")
		}
		return pass(section, name)
	}
	if err == nil {
		return fail(section, name, "expected verification to fail, it succeeded")
	}
	return pass(section, name)
}

func equalStrings(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

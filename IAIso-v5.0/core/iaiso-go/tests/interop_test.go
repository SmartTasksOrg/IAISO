// Package tests holds cross-port interoperability checks.
//
// A consent token is a wire artifact. If the Go SDK cannot verify a token
// minted by the Python or Rust SDK against the shared conformance key, the
// ports do not interoperate, whatever their unit tests say. These vectors
// are the same bytes every port checks against.
package tests

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/iaiso/iaiso-go/iaiso/conformance"
	"github.com/iaiso/iaiso-go/iaiso/consent"
)

func specRoot() string { return filepath.Join("..", "spec") }

// TestConformanceVectors runs all 67 spec vectors under `go test`, so a
// regression fails CI rather than waiting for someone to run the binary.
func TestConformanceVectors(t *testing.T) {
	results, err := conformance.RunAll(specRoot())
	if err != nil {
		t.Fatal(err)
	}
	for _, f := range results.Failures() {
		t.Errorf("[%s] %s: %s", f.Section, f.Name, f.Message)
	}
	passed, total := results.CountPassed()
	if passed != total {
		t.Fatalf("conformance: %d/%d vectors passed", passed, total)
	}
	if total != 72 {
		t.Fatalf("expected 72 vectors, found %d — the spec moved and this port has not", total)
	}
}

func sharedKey(t *testing.T) []byte {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(specRoot(), "consent", "vectors.json"))
	if err != nil {
		t.Fatal(err)
	}
	var file struct {
		HS256KeyShared string `json:"hs256_key_shared"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		t.Fatal(err)
	}
	if file.HS256KeyShared == "" {
		t.Fatal("spec/consent/vectors.json has no hs256_key_shared")
	}
	return []byte(file.HS256KeyShared)
}

// TestGoIssuedTokenVerifiesUnderSharedKey is the outbound half of interop:
// a token this SDK mints must be verifiable by any port holding the shared
// key. We verify with a freshly constructed verifier that shares nothing
// with the issuer but the key and the clock.
func TestGoIssuedTokenVerifiesUnderSharedKey(t *testing.T) {
	const now = 1_700_000_000
	key := sharedKey(t)

	issuer, err := consent.NewIssuer(consent.IssuerOptions{
		SigningKey: key, Algorithm: consent.HS256,
		Issuer: "iaiso", Clock: consent.FixedClock(now),
	})
	if err != nil {
		t.Fatal(err)
	}
	issued, err := issuer.Issue(consent.IssueParams{
		Subject: "interop-subject", Scopes: []string{"tools.search", "billing"},
		ExecutionID: "exec-interop", TTLSeconds: 3600,
	})
	if err != nil {
		t.Fatal(err)
	}

	verifier, err := consent.NewVerifier(consent.VerifierOptions{
		VerificationKey: key, Algorithm: consent.HS256,
		Issuer: "iaiso", Clock: consent.FixedClock(now + 10),
	})
	if err != nil {
		t.Fatal(err)
	}
	scope, err := verifier.Verify(issued.Token, "exec-interop")
	if err != nil {
		t.Fatalf("a Go-issued token failed verification under the shared key: %v", err)
	}
	if scope.Subject != "interop-subject" {
		t.Fatalf("subject = %q", scope.Subject)
	}
	if !scope.Grants("tools.search.web") {
		t.Fatal("prefix grant lost across the wire")
	}
}

// TestForeignIssuedTokenVerifies is the inbound half: every valid_tokens
// vector was minted by the reference (Python) implementation, not by Go.
func TestForeignIssuedTokenVerifies(t *testing.T) {
	key := sharedKey(t)
	raw, err := os.ReadFile(filepath.Join(specRoot(), "consent", "vectors.json"))
	if err != nil {
		t.Fatal(err)
	}
	var file struct {
		ValidTokens []struct {
			Name        string  `json:"name"`
			Token       string  `json:"token"`
			Issuer      string  `json:"issuer"`
			Now         int64   `json:"now"`
			ExecutionID *string `json:"execution_id"`
			Expected    struct {
				Sub string `json:"sub"`
			} `json:"expected"`
		} `json:"valid_tokens"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		t.Fatal(err)
	}
	if len(file.ValidTokens) == 0 {
		t.Fatal("no valid_tokens vectors")
	}
	for _, v := range file.ValidTokens {
		t.Run(v.Name, func(t *testing.T) {
			issuerName := v.Issuer
			if issuerName == "" {
				issuerName = "iaiso"
			}
			verifier, err := consent.NewVerifier(consent.VerifierOptions{
				VerificationKey: key, Algorithm: consent.HS256,
				Issuer: issuerName, Clock: consent.FixedClock(v.Now),
			})
			if err != nil {
				t.Fatal(err)
			}
			execID := ""
			if v.ExecutionID != nil {
				execID = *v.ExecutionID
			}
			scope, err := verifier.Verify(v.Token, execID)
			if err != nil {
				t.Fatalf("foreign-issued token rejected: %v", err)
			}
			if scope.Subject != v.Expected.Sub {
				t.Fatalf("sub = %q, want %q", scope.Subject, v.Expected.Sub)
			}
		})
	}
}

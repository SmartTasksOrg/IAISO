// Package consent implements IAIso consent tokens: signed, scoped,
// expiring JWTs (HS256 or RS256) that gate sensitive or expensive
// operations.
//
// Scope grammar (spec/consent/README.md):
//
//	scope   ::= segment ("." segment)*
//	segment ::= [a-z0-9_-]+
//
// A token granting G satisfies a request for R iff G == R (exact match) or
// R begins with G + "." (prefix at a segment boundary). "tools" grants
// "tools.search"; it does not grant "toolsbar". Matching is case-sensitive.
package consent

import (
	"errors"
	"fmt"
	"strings"
)

// Sentinel errors. Callers should branch on these rather than on message text.
var (
	// ErrInvalidToken covers bad signatures, wrong issuer, missing claims
	// and execution-binding mismatches.
	ErrInvalidToken = errors.New("invalid token")
	// ErrExpiredToken means exp (plus leeway) is in the past.
	ErrExpiredToken = errors.New("expired token")
	// ErrRevokedToken means the jti is on the revocation list.
	ErrRevokedToken = errors.New("revoked token")
	// ErrInsufficientScope means the token is valid but grants too little.
	ErrInsufficientScope = errors.New("insufficient scope")
	// ErrEmptyRequestedScope means ScopeGranted was asked about "".
	ErrEmptyRequestedScope = errors.New("requested scope must be non-empty")
	// ErrSigningFailed wraps key-loading and signing failures.
	ErrSigningFailed = errors.New("signing failed")
	// ErrUnsupportedAlgorithm rejects anything but HS256 and RS256.
	// "none" is intentionally absent: verifiers MUST reject unsigned tokens.
	ErrUnsupportedAlgorithm = errors.New("unsupported algorithm")
)

// Algorithm is a supported JWT signature algorithm.
type Algorithm string

const (
	// HS256 is symmetric: the verifier holds the same secret that signs.
	// A compromised host can therefore forge tokens. See LIMITATIONS.md.
	HS256 Algorithm = "HS256"
	// RS256 is asymmetric: the verifier holds only the public key.
	// Prefer it wherever the verifier and the issuer are separate hosts.
	RS256 Algorithm = "RS256"
)

// String returns the wire-format algorithm name.
func (a Algorithm) String() string { return string(a) }

// Valid reports whether a is a supported algorithm.
func (a Algorithm) Valid() bool { return a == HS256 || a == RS256 }

// ScopeGranted reports whether any granted scope satisfies requested.
// An empty requested scope is an error, not a false: silently answering
// "not granted" would hide a caller bug behind a denial.
func ScopeGranted(granted []string, requested string) (bool, error) {
	if requested == "" {
		return false, ErrEmptyRequestedScope
	}
	for _, g := range granted {
		if g == requested {
			return true, nil
		}
		if strings.HasPrefix(requested, g+".") {
			return true, nil
		}
	}
	return false, nil
}

// ValidScopeString reports whether s matches the scope grammar.
func ValidScopeString(s string) bool {
	if s == "" {
		return false
	}
	for _, seg := range strings.Split(s, ".") {
		if seg == "" {
			return false
		}
		for _, r := range seg {
			switch {
			case r >= 'a' && r <= 'z':
			case r >= '0' && r <= '9':
			case r == '_' || r == '-':
			default:
				return false
			}
		}
	}
	return true
}

// Scope is a verified consent token, ready to attach to an execution.
type Scope struct {
	Token       string
	Subject     string
	Scopes      []string
	ExecutionID string
	JTI         string
	IssuedAt    int64
	ExpiresAt   int64
	Metadata    map[string]any
}

// Grants reports whether the scope satisfies requested.
func (s *Scope) Grants(requested string) bool {
	ok, err := ScopeGranted(s.Scopes, requested)
	return err == nil && ok
}

// Require returns ErrInsufficientScope unless the scope satisfies requested.
//
// Gate cost-bearing paths on this: the frontier-model call, the expensive
// retrieval. A scope check is the cheapest way to make an expensive
// operation require explicit authorisation.
func (s *Scope) Require(requested string) error {
	if !s.Grants(requested) {
		return fmt.Errorf("%w: %q not granted by token (granted: %v)",
			ErrInsufficientScope, requested, s.Scopes)
	}
	return nil
}

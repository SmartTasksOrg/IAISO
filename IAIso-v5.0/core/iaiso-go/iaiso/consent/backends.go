package consent

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/pem"
	"fmt"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// Claims is the consent-token wire format. It embeds jwt.RegisteredClaims
// for iss/sub/iat/exp/jti and adds the IAIso-specific claims.
type Claims struct {
	Scopes      []string       `json:"scopes"`
	ExecutionID string         `json:"execution_id,omitempty"`
	Metadata    map[string]any `json:"metadata,omitempty"`
	jwt.RegisteredClaims
}

// Clock returns Unix seconds. Injected so verification is deterministic in
// tests and in the conformance vectors, which supply a fixed `now`.
type Clock func() int64

// SystemClock is the default Clock.
func SystemClock() Clock { return func() int64 { return time.Now().Unix() } }

// FixedClock always returns t. Used by the conformance runner.
func FixedClock(t int64) Clock { return func() int64 { return t } }

// RevocationList is an in-memory jti denylist. Production deployments
// should back this with Redis or an equivalent shared store — an in-process
// list revokes nothing for the other twenty workers.
type RevocationList struct {
	mu      sync.RWMutex
	revoked map[string]struct{}
}

// NewRevocationList returns an empty list.
func NewRevocationList() *RevocationList {
	return &RevocationList{revoked: map[string]struct{}{}}
}

// Revoke adds a jti to the list.
func (r *RevocationList) Revoke(jti string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.revoked[jti] = struct{}{}
}

// IsRevoked reports membership.
func (r *RevocationList) IsRevoked(jti string) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	_, ok := r.revoked[jti]
	return ok
}

// Size reports how many jtis are revoked.
func (r *RevocationList) Size() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.revoked)
}

// GenerateHS256Secret returns a 64-byte (512-bit) base64url secret, well
// above the HS256 minimum.
//
// A key generated here has never been written down. Under enforcement_mode:
// strict an auto-generated HS256 key is a boot failure, because nothing
// else can verify the tokens it signs.
func GenerateHS256Secret() (string, error) {
	buf := make([]byte, 64)
	if _, err := rand.Read(buf); err != nil {
		return "", fmt.Errorf("%w: %v", ErrSigningFailed, err)
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}

func generateJTI() string {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return fmt.Sprintf("%032x", time.Now().UnixNano())
	}
	return hex.EncodeToString(buf)
}

// parseRSAPrivateKey accepts PKCS#1 or PKCS#8 PEM.
func parseRSAPrivateKey(pemBytes []byte) (*rsa.PrivateKey, error) {
	block, _ := pem.Decode(pemBytes)
	if block == nil {
		return nil, fmt.Errorf("%w: no PEM block in RSA private key", ErrSigningFailed)
	}
	if k, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return k, nil
	}
	any, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrSigningFailed, err)
	}
	k, ok := any.(*rsa.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("%w: PKCS#8 key is not RSA", ErrSigningFailed)
	}
	return k, nil
}

// parseRSAPublicKey accepts a PKIX public key PEM, or a certificate, or an
// RSA private key PEM (from which the public half is taken).
func parseRSAPublicKey(pemBytes []byte) (*rsa.PublicKey, error) {
	block, _ := pem.Decode(pemBytes)
	if block == nil {
		return nil, fmt.Errorf("%w: no PEM block in RSA verification key", ErrInvalidToken)
	}
	if pub, err := x509.ParsePKIXPublicKey(block.Bytes); err == nil {
		if rp, ok := pub.(*rsa.PublicKey); ok {
			return rp, nil
		}
		return nil, fmt.Errorf("%w: PKIX key is not RSA", ErrInvalidToken)
	}
	if pub, err := x509.ParsePKCS1PublicKey(block.Bytes); err == nil {
		return pub, nil
	}
	if priv, err := parseRSAPrivateKey(pemBytes); err == nil {
		return &priv.PublicKey, nil
	}
	return nil, fmt.Errorf("%w: unrecognised RSA verification key", ErrInvalidToken)
}

func unixTime(sec int64) time.Time { return time.Unix(sec, 0).UTC() }

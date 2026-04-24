# IAIso ConsentScope — Normative Specification

**Version: 1.0**

A ConsentScope is a JSON Web Token ([RFC 7519](https://www.rfc-editor.org/rfc/rfc7519))
that grants a named subject permission to perform a specific set of
actions within a specific time window and, optionally, within a specific
IAIso execution.

## 1. Signing algorithms

Conformant implementations MUST support:

- **HS256** — HMAC-SHA256, symmetric, same key signs and verifies.
- **RS256** — RSA-SHA256, asymmetric, private key signs, public key verifies.

Conformant implementations MAY additionally support ES256, EdDSA, PS256.
If they do, they MUST be opt-in and explicitly configured — not enabled
automatically based on the token's `alg` header (that would defeat the
point of requiring a specific algorithm).

Conformant implementations MUST reject tokens signed with the JWT `none`
algorithm, whatever the caller passes to the verifier.

## 2. Required claims

These claims MUST be present in every IAIso ConsentScope:

| Claim    | Type   | Meaning                                                       |
|----------|--------|---------------------------------------------------------------|
| `iss`    | string | Issuer identity. Verifier MUST check equality with its config.|
| `sub`    | string | Subject — the entity the token authorizes.                    |
| `iat`    | number | Issued-at, Unix seconds. Integer.                             |
| `exp`    | number | Expiry, Unix seconds. Integer. MUST be > `iat`.               |
| `jti`    | string | Unique token ID. Used for revocation.                         |
| `scopes` | array of string | Granted scopes. See §4.                              |

A verifier MUST reject a token missing any of these claims.

## 3. Optional claims

| Claim           | Type    | Meaning                                                       |
|-----------------|---------|---------------------------------------------------------------|
| `execution_id`  | string  | If present, token is valid only for this execution.           |
| `metadata`      | object  | Caller-defined additional claims. Propagated to audit events. |

Unknown claims MUST be ignored. Implementations MUST NOT reject a token
for containing additional claims they do not recognize. This is how the
format evolves without breaking deployed verifiers.

## 4. Scope grammar

A scope is a dot-separated sequence of segments:

```
scope    ::= segment ("." segment)*
segment  ::= 1*( lowercase-letter / digit / "_" / "-" )
```

The ABNF:

```
segment = 1*segment-char
segment-char = %x61-7A / %x30-39 / %x5F / %x2D
             ; a-z / 0-9 / _ / -
```

Scopes are case-sensitive. Uppercase characters are invalid.

Examples of valid scopes:

- `tools`
- `tools.search`
- `admin.user.create`
- `api-v2.read`

Examples of invalid scopes:

- `` (empty)
- `.` (empty segment)
- `tools.` (trailing dot)
- `Tools` (uppercase)
- `tools:search` (invalid character)

## 5. Scope matching (prefix-match at segment boundaries)

A token that grants scope `G` satisfies a request for scope `R` if and
only if:

1. **Exact match**: `G == R`, or
2. **Prefix match at segment boundary**: `R` starts with `G + "."`.

This is the ONLY scope-matching algorithm. No glob, no wildcard, no
substring.

### Consequences

- `tools` grants `tools.search` (prefix at boundary) ✓
- `tools` grants `tools.anything.deeply.nested` (prefix at boundary) ✓
- `tools` does NOT grant `admin.tools` (not a prefix) ✗
- `tools` does NOT grant `tool` (not a prefix — partial word) ✗
- `tools` does NOT grant `toolsbar` (prefix but not at boundary) ✗
- `tools.search` grants `tools.search.bulk` ✓
- `tools.search` does NOT grant `tools.fetch` ✗
- `tools.search` does NOT grant `tools` (cannot grant more than yourself) ✗

### Test procedure

Given granted scopes `G = [g1, g2, ...]` and requested scope `R`, the
check `grants(G, R)` is:

```
for each g in G:
    if g == R:
        return true
    if R starts with (g + "."):
        return true
return false
```

## 6. Verification procedure

A conformant verifier, given a token string `token`, a verification
key, a configured issuer string, an expected algorithm, and optionally
a revocation list and an execution_id to bind:

1. **Decode header**. Parse the JOSE header. If `alg` is not the
   configured algorithm, reject with `InvalidToken`. If `alg` is `none`,
   reject with `InvalidToken`.

2. **Verify signature** using the configured key.
   On failure, reject with `InvalidToken`.

3. **Check required claims** are present (§2).
   On failure, reject with `InvalidToken`.

4. **Check `iss`** equals the configured issuer.
   On failure, reject with `InvalidToken`.

5. **Check `exp`** is in the future, allowing configured clock-skew
   leeway (default 5 seconds). On failure, reject with `ExpiredToken`.

6. **Check revocation**: if a revocation list is configured, look up
   `jti`. If revoked, reject with `RevokedToken`.

7. **Check execution binding**: if the call specified an `execution_id`
   AND the token has an `execution_id` claim, they MUST be equal. Mismatch:
   `InvalidToken`. If either side is absent, binding is not enforced.

8. **Construct and return a verified ConsentScope** carrying the
   decoded claims.

### Scope checking

Scope-matching happens AT THE CALL SITE, not at token verification.
A valid token that grants no scopes is a valid empty-authorization token;
trying to use it for any scope raises `InsufficientScope`.

## 7. Error model

A conformant implementation MUST expose four distinguishable error kinds:

| Error                 | When raised                                                     |
|-----------------------|-----------------------------------------------------------------|
| `InvalidToken`        | Signature, algorithm, missing claims, wrong issuer, wrong exec. |
| `ExpiredToken`        | `exp` in the past (past the leeway).                            |
| `RevokedToken`        | `jti` on the revocation list.                                   |
| `InsufficientScope`   | Valid token but doesn't grant the requested scope.              |

The language-specific error types MAY be named differently idiomatically
(e.g., `ConsentError.Expired` in Rust, `TokenExpiredException` in Java).
They MUST be distinguishable to callers — catching "invalid" MUST NOT
also catch "expired" — because callers need to react differently
(refresh vs. re-authenticate vs. escalate).

## 8. Test vectors

`spec/consent/vectors.json` contains three vector kinds:

- **Scope-match vectors**: pure `grants(G, R) -> bool` checks; no JWT
  math. These are the cheapest to port and should be the first check
  a new implementation passes.
- **Token-shape vectors**: valid and invalid decoded-claim payloads.
  Tests the required/optional claim rules.
- **End-to-end vectors**: issue-and-verify round trips with HS256 keys,
  exercising the full pipeline.

RS256 end-to-end vectors are in `spec/consent/vectors.json` as well, but
use a deterministic RSA keypair (fixed in the vector file). Real
implementations MUST NOT use this keypair for anything other than
running conformance tests.

## 9. Security considerations

These are implementation obligations, not optional recommendations:

- **No `alg=none`.** See §1.
- **No algorithm confusion.** A verifier configured for RS256 MUST NOT
  accept HS256 tokens even if the signature would verify against the
  RSA public key interpreted as an HMAC key.
- **Constant-time signature comparison** for HS256.
- **Secret entropy.** HS256 secrets MUST be at least 256 bits of CSPRNG
  output. The reference implementation provides
  `generate_hs256_secret()`; ports MUST provide an equivalent.
- **Store secrets in a secret manager.** Not in source, not in logs,
  not in audit events. The `metadata` claim is propagated to audit;
  callers MUST NOT put secrets there.
- **Short TTLs.** Default 1 hour. Tokens valid for longer than 24 hours
  SHOULD require explicit opt-in.

## 10. Relationship to OIDC

IAIso tokens are distinct from OIDC access tokens. See `spec/identity/`
(not yet authored; see `iaiso.identity` in the Python reference) for
how to map OIDC claims (`scp`, `groups`, `roles`) into IAIso scopes
and, if desired, mint an IAIso-signed token from a verified OIDC
identity.

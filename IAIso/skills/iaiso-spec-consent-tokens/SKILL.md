---
name: iaiso-spec-consent-tokens
description: "Use this skill when issuing, verifying, or debugging IAIso consent tokens (JWTs). Triggers on `iss`, `sub`, `jti`, `scopes`, `execution_id`, HS256, RS256, the scope grammar, or prefix-match scope checking. Do not use it to set up an OIDC bridge — see the `iaiso-deploy-oidc-*` skills."
version: 1.0.0
tier: P0
category: spec
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso ConsentScope tokens — implementation contract

## When this applies

A token is being issued, verified, decoded, or debugged. Scope
grammar questions belong here too. The normative source is
`core/spec/consent/README.md` and `consent/vectors.json`.

## Steps To Complete

1. **Use a supported algorithm.** Conformant verifiers MUST
   support HS256 and RS256. They MAY support ES256 / EdDSA /
   PS256 only if explicitly opted in via configuration — never
   trust the token's `alg` header to decide. The `none`
   algorithm MUST be rejected.

2. **Require all six core claims** on every token:

   | Claim    | Type   | Meaning                                         |
   |----------|--------|-------------------------------------------------|
   | `iss`    | string | issuer; verifier checks equality with config    |
   | `sub`    | string | subject — the entity authorised                 |
   | `iat`    | number | issued-at, Unix seconds, integer                |
   | `exp`    | number | expiry, Unix seconds, integer; `exp > iat`      |
   | `jti`    | string | unique token id; revocation key                 |
   | `scopes` | array  | array of grant strings; see scope grammar       |

   Optional: `execution_id` (binds the token to a specific
   execution), `metadata` (free object, propagated to audit).
   Unknown claims MUST be ignored, not rejected.

3. **Apply the scope grammar.** A scope is a dot-separated
   sequence of segments where each segment is `[a-z0-9_-]+`.
   Uppercase, empty segments, leading/trailing dots, and
   characters outside the set are invalid.

   Valid: `tools`, `tools.search`, `admin.user.create`,
   `api-v2.read`.

   Invalid: empty, `.`, `tools.`, `Tools`, `tools:search`.

4. **Match scopes by prefix at segment boundary.** A granted
   scope `G` satisfies a request `R` iff `G == R` OR
   `R` starts with `G + "."`. Nothing else — no glob, no
   wildcard, no substring.

   - `tools` grants `tools.search` ✓
   - `tools` grants `tools.x.y.z` ✓
   - `tools` does NOT grant `toolsbar` ✗ (boundary missing)
   - `tools.search` does NOT grant `tools` ✗ (cannot grant up)
   - `tools.search` does NOT grant `tools.fetch` ✗

5. **Run the verification procedure in order.** Stop on first
   failure with the documented error type:

   1. parse JOSE header; reject `none` and any unconfigured `alg`
      with `InvalidToken`;
   2. verify signature with the configured key — `InvalidToken` on fail;
   3. assert all six core claims present — `InvalidToken` on fail;
   4. assert `iss` equals configured issuer — `InvalidToken`;
   5. assert `exp` is in the future with skew leeway (default 5s)
      — `ExpiredToken`;
   6. check revocation list by `jti` — `RevokedToken`;
   7. if both call and token specify `execution_id`, they must
      match — `InvalidToken`;
   8. construct and return the verified ConsentScope.

## Common mistakes

- Treating `metadata` as confidential. It is signed but
  readable to anyone with the token. Place secrets elsewhere.
- Assuming the revocation list is strongly consistent. It is
  eventually consistent — agents that cached a verified scope
  will see revocation at next re-verify.
- Using the same HS256 secret across environments. Rotate per
  environment and per role.

## What this skill does NOT cover

- Bridging external IdPs into IAIso — see
  `../iaiso-deploy-oidc-okta/SKILL.md` and friends.
- Provisioning the issuer — see
  `../iaiso-deploy-consent-issuance/SKILL.md`.

## References

- `core/spec/consent/README.md` (normative)
- `core/spec/consent/vectors.json` (23 conformance vectors)
- `core/spec/consent/claims.schema.json`

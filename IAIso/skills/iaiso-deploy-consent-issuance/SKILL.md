---
name: iaiso-deploy-consent-issuance
description: "Use this skill when standing up the consent-token pipeline — who issues, with what key, into what audience. Do not use it for verifying tokens — see `iaiso-spec-consent-tokens`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Provisioning the IAIso consent issuer

## When this applies

First deployment, or when adding a new issuer for a new
environment / tenant. The token issuer is the trust anchor
for every privileged action — get it right.

## Steps To Complete

1. **Choose HS256 vs RS256.**

   - HS256: symmetric. Issuer and verifier share a 64-byte
     secret. Simpler, faster (~30µs verify). Use within a
     single trust boundary.
   - RS256: asymmetric. Issuer holds private key, verifiers
     hold public key. Use when verifiers and issuer cross
     trust boundaries (multi-team, multi-tenant, third-party
     integrations).

2. **Generate keys with the SDK helper.**

   ```python
   from iaiso.consent import Issuer
   secret = Issuer.generate_hs256_secret()  # base64url, no pad
   ```

   For RS256 use `openssl genpkey -algorithm RSA -out
   private.pem -pkeyopt rsa_keygen_bits:2048` (or the SDK
   helper).

3. **Pick a stable issuer string.** The verifier's `iss`
   check is byte-equal. Use a URL-shaped identifier
   (`https://iaiso.example.com/prod`) so it doubles as a
   JWKS pointer if you publish keys.

4. **Set sensible defaults:**

   ```yaml
   consent:
     issuer: "iaiso-prod"
     default_ttl_seconds: 1800           # 30 minutes
     allowed_algorithms: [HS256]
   ```

   Long TTLs delay revocation; short TTLs cost re-issuance.
   30 minutes is a reasonable starting point.

5. **Stand up a revocation list backend.** In-memory is dev
   only. For prod use Redis with a TTL slightly longer than
   max token lifetime (so revoked-then-expired tokens fall
   off the list cleanly).

6. **Rotate keys on a schedule.** The reference SDK supports
   a key id (`kid`) header and a verifier that holds multiple
   active keys. Rotate quarterly minimum; immediately on
   compromise.

## What you NEVER do

- Reuse keys across environments. Dev secrets leak; prod
  secrets must not be among them.
- Issue tokens with TTL > 24h without a strong reason. The
  framework's revocation model is eventually consistent;
  long TTLs are blast-radius extenders.
- Put secrets inside the JWT `metadata` field. It is signed
  but readable by anyone with the token.

## What this skill does NOT cover

- Bridging external IdPs — see `iaiso-deploy-oidc-*`.
- Token verification semantics — see
  `../iaiso-spec-consent-tokens/SKILL.md`.

## References

- `core/iaiso-python/iaiso/consent/`
- `core/iaiso-php/src/Consent/Issuer.php` (reference)

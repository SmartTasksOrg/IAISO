---
name: iaiso-deploy-oidc-auth0
description: "Use this skill when bridging Auth0 identities into IAIso consent scopes. Triggers on Auth0 OIDC, JWKS, group-claim mapping, or scope translation from Auth0 into IAIso. Do not use it for the consent issuer itself — see `iaiso-deploy-consent-issuance`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Auth0 → IAIso ConsentScope bridge

## When this applies

Users / service accounts authenticate via Auth0; you
want their identity to flow through to IAIso ConsentScopes
rather than running a parallel issuer.

## Steps To Complete

1. **Configure the Auth0 OIDC client.** Standard scopes
   (`openid`, `profile`), plus any custom scope or claim that
   carries the IAIso scope grant.

2. **Trust Auth0's signing keys.** Use Auth0's JWKS endpoint at `/.well-known/jwks.json`. Custom claims must be namespaced (Auth0 enforces this); expect `https://your-app/iaiso_scopes` rather than bare `iaiso_scopes`.

3. **Map Auth0 claims to IAIso scopes.** Pick one:

   - **Direct claim**: a custom `iaiso_scopes` claim on the
     Auth0 token, set in the IdP. Map 1:1 into
     `scopes` on the IAIso token.
   - **Group → scope translation**: read the Auth0 group
     membership claim, look up the mapping table at the
     bridge, write the resulting scopes into the IAIso token.

   Group-to-scope mapping typically lives in an Auth0 Action; the bridge can also drive it from the user's app metadata.

4. **Re-issue as an IAIso ConsentScope.** Do not pass the
   Auth0 JWT directly into the IAIso engine — IAIso
   expects its own envelope (claim names, scope grammar,
   `execution_id` binding). The bridge verifies the
   Auth0 token, then issues a fresh IAIso token with a
   short TTL.

5. **Bind the IAIso token to an execution_id when possible.**
   This converts a stolen-token replay into a per-execution
   blast radius rather than a per-account one.

6. **Audit the bridge.** Log every Auth0-token-in →
   IAIso-token-out so revocation upstream can be traced
   through to which IAIso tokens were issued under it.

## What this skill does NOT cover

- The IAIso token format — see
  `../iaiso-spec-consent-tokens/SKILL.md`.
- Other IdPs — see the matching `iaiso-deploy-oidc-*` skill.

## References

- `vision/systems/identity/auth0/README.md`
- `core/iaiso-python/iaiso/identity/`

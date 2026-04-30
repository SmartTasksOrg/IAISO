---
name: iaiso-deploy-oidc-okta
description: "Use this skill when bridging Okta identities into IAIso consent scopes. Triggers on Okta OIDC, JWKS, group-claim mapping, or scope translation from Okta into IAIso. Do not use it for the consent issuer itself — see `iaiso-deploy-consent-issuance`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Okta → IAIso ConsentScope bridge

## When this applies

Users / service accounts authenticate via Okta; you
want their identity to flow through to IAIso ConsentScopes
rather than running a parallel issuer.

## Steps To Complete

1. **Configure the Okta OIDC client.** Standard scopes
   (`openid`, `profile`), plus any custom scope or claim that
   carries the IAIso scope grant.

2. **Trust Okta's signing keys.** Pull JWKS from `https://<your-org>.okta.com/oauth2/default/v1/keys` and rotate from there; do not pin individual keys.

3. **Map Okta claims to IAIso scopes.** Pick one:

   - **Direct claim**: a custom `iaiso_scopes` claim on the
     Okta token, set in the IdP. Map 1:1 into
     `scopes` on the IAIso token.
   - **Group → scope translation**: read the Okta group
     membership claim, look up the mapping table at the
     bridge, write the resulting scopes into the IAIso token.

   Okta groups map cleanly via the `groups` claim if you enabled it on the auth server.

4. **Re-issue as an IAIso ConsentScope.** Do not pass the
   Okta JWT directly into the IAIso engine — IAIso
   expects its own envelope (claim names, scope grammar,
   `execution_id` binding). The bridge verifies the
   Okta token, then issues a fresh IAIso token with a
   short TTL.

5. **Bind the IAIso token to an execution_id when possible.**
   This converts a stolen-token replay into a per-execution
   blast radius rather than a per-account one.

6. **Audit the bridge.** Log every Okta-token-in →
   IAIso-token-out so revocation upstream can be traced
   through to which IAIso tokens were issued under it.

## What this skill does NOT cover

- The IAIso token format — see
  `../iaiso-spec-consent-tokens/SKILL.md`.
- Other IdPs — see the matching `iaiso-deploy-oidc-*` skill.

## References

- `vision/systems/identity/okta/README.md`
- `core/iaiso-python/iaiso/identity/`

---
name: iaiso-deploy-oidc-azure-ad
description: "Use this skill when bridging Azure AD identities into IAIso consent scopes. Triggers on Azure AD OIDC, JWKS, group-claim mapping, or scope translation from Azure AD into IAIso. Do not use it for the consent issuer itself — see `iaiso-deploy-consent-issuance`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Azure AD → IAIso ConsentScope bridge

## When this applies

Users / service accounts authenticate via Azure AD; you
want their identity to flow through to IAIso ConsentScopes
rather than running a parallel issuer.

## Steps To Complete

1. **Configure the Azure AD OIDC client.** Standard scopes
   (`openid`, `profile`), plus any custom scope or claim that
   carries the IAIso scope grant.

2. **Trust Azure AD's signing keys.** Use the tenant-scoped issuer `https://login.microsoftonline.com/<tenant-id>/v2.0` and the corresponding JWKS. Restrict accepted issuers to your tenant; the multi-tenant default is usually wrong.

3. **Map Azure AD claims to IAIso scopes.** Pick one:

   - **Direct claim**: a custom `iaiso_scopes` claim on the
     Azure AD token, set in the IdP. Map 1:1 into
     `scopes` on the IAIso token.
   - **Group → scope translation**: read the Azure AD group
     membership claim, look up the mapping table at the
     bridge, write the resulting scopes into the IAIso token.

   App-role claims (`roles`) are the most stable mapping target; group claims can hit Azure AD's overage problem on >150 groups and require Graph lookups.

4. **Re-issue as an IAIso ConsentScope.** Do not pass the
   Azure AD JWT directly into the IAIso engine — IAIso
   expects its own envelope (claim names, scope grammar,
   `execution_id` binding). The bridge verifies the
   Azure AD token, then issues a fresh IAIso token with a
   short TTL.

5. **Bind the IAIso token to an execution_id when possible.**
   This converts a stolen-token replay into a per-execution
   blast radius rather than a per-account one.

6. **Audit the bridge.** Log every Azure AD-token-in →
   IAIso-token-out so revocation upstream can be traced
   through to which IAIso tokens were issued under it.

## What this skill does NOT cover

- The IAIso token format — see
  `../iaiso-spec-consent-tokens/SKILL.md`.
- Other IdPs — see the matching `iaiso-deploy-oidc-*` skill.

## References

- `vision/systems/identity/azure-ad/README.md`
- `core/iaiso-python/iaiso/identity/`

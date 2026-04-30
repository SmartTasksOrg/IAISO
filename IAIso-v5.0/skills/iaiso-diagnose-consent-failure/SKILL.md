---
name: iaiso-diagnose-consent-failure
description: "Use this skill when consent checks are failing more than expected. Triggers on `consent.denied` rate spikes, `ConsentMissing` errors. Do not use it for token issuance problems — see `iaiso-deploy-consent-issuance`."
version: 1.0.0
tier: P3
category: diagnostics
framework: IAIso v5.0
license: See ../LICENSE
---

# Diagnosing consent failures

## When this applies

Agents are hitting `ConsentMissing`, `ConsentDenied`,
`ConsentExpired`, or `ConsentRevoked` more often than expected.

## Steps To Complete

1. **Group failures by failure type.** Each implies different
   root cause:

   - `ConsentMissing` → no token attached. Probably a wiring
     issue: which call path attaches the token, and where is
     it not being threaded through?
   - `ConsentDenied` → scope mismatch. The agent's tool needs
     `X` but the token grants `Y`.
   - `ConsentExpired` → TTL too short for the workload, or
     clock skew between issuer and verifier.
   - `ConsentRevoked` → revocation list growing? Active
     incident? Key rotation in progress?

2. **For `ConsentDenied`, list the (granted_scope,
   requested_scope) pairs.** A pattern like every `tools.read`
   token failing on `tools.write` requests is a config
   mismatch.

3. **For `ConsentExpired`, check `iat` vs `exp` distribution
   and verifier clock.** Skew over a few seconds means
   NTP problems; skew minutes means real clock drift.

4. **For `ConsentRevoked` spikes**, check the revocation
   list backend. Did someone bulk-revoke?

5. **Audit who issues vs who verifies.** Mismatch in
   configured `iss` between the two ends produces
   `InvalidToken` failures that look like misconfiguration.

## What this skill does NOT cover

- Issuing tokens — see
  `../iaiso-deploy-consent-issuance/SKILL.md`.

## References

- `core/spec/consent/README.md`

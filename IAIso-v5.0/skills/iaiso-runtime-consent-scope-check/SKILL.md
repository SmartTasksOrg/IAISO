---
name: iaiso-runtime-consent-scope-check
description: "Use this skill before every tool call, every external API call, every privileged action. Triggers any time the agent considers an action that has a `scope:` annotation. Do not skip it 'because the action is read-only' — read access is still scoped under IAIso."
version: 1.0.0
tier: P0
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Consent-scope check before action

## When this applies

The agent is about to do something privileged: call a tool,
hit an external API, write to a database, send a notification,
move money, mutate state. Every such action passes through
this check.

## Steps To Complete

1. **Resolve the requested scope string.** Most actions have a
   `scope:` annotation in your tool registry. Resolve it
   before invoking; never let the action invent its own scope
   at runtime.

2. **Call the SDK's scope verifier:**

   ```python
   try:
       verified = consent.check(execution.token, scope=requested_scope)
   except ConsentMissing:
       # no token attached at all
       ...
   except ConsentDenied:
       # token does not grant the requested scope
       ...
   except ConsentExpired:
       # token expired
       ...
   except ConsentRevoked:
       # jti on revocation list
       ...
   ```

3. **Branch on the failure mode:**

   - `ConsentMissing` → halt, emit `consent.missing`, request
     a token. Do not proceed.
   - `ConsentDenied`  → halt, emit `consent.denied`. Do NOT
     retry with a broader scope; that is exactly the proxy-
     optimization the framework forbids. Hand to
     `iaiso-runtime-handle-escalation`.
   - `ConsentExpired` → request a refresh; treat the original
     action as not-yet-attempted.
   - `ConsentRevoked` → halt; emit `consent.denied` with
     reason `revoked`. Surface to operations — revoked tokens
     hitting agents in production usually signals key rotation
     or an active incident.

4. **Attach metadata for traceability.** When you do invoke
   the action, ensure the `metadata` field on the consent
   check propagates into audit. Investigators use it to link
   "user X requested action Y" to "agent decided Z".

5. **Cache verified scopes only briefly.** Verifying takes
   ~30µs (HS256). The temptation to skip the verifier on
   repeat actions makes revocation ineffective — keep TTLs
   short or re-verify each call.

## What you NEVER do

- Read claims without verifying signature. Claims you read
  that way are attacker-controlled.
- Pattern-match on scope substrings. Use the SDK's
  prefix-at-segment-boundary algorithm.
- Up-grant. A scope of `tools.search` does not grant `tools` —
  that direction is forbidden.

## What this skill does NOT cover

- Issuing the tokens — see
  `../iaiso-deploy-consent-issuance/SKILL.md`.
- The grammar in detail — see
  `../iaiso-spec-consent-tokens/SKILL.md`.

## References

- `core/spec/consent/README.md`
- `vision/templates/consent-enforcement.template`

---
name: iaiso-runtime-model-provenance-guard
description: "Use this skill to apply the IAIso model_provenance_guard: a Layer 5 consent-bounded control that fails closed on model/artifact loads with caller-supplied paths and remote-code trust. Load it whenever an agent or pipeline can trigger a from_pretrained-style load of a non-allowlisted source. Do not use it as a general input sanitizer or as a substitute for a Layer 0 anchor against an in-process adversary."
version: 1.0.0
tier: P2
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Control — model-provenance guard (Layer 5, invariant #4)

## When this applies

A code path can load a model/artifact whose source path is caller- or
agent-supplied and whose loading executes remote/custom code (the
`trust_remote_code=True` shape). This is a consent-bounded-expansion
concern: loading untrusted code is an expansion of authority that must be
gated by a signed ConsentScope, fail-closed.

## Steps To Complete

1. **Interpose before the real loader.** Wrap the load call so the guard
   runs first. This is Tier 2 (strap-on) in the proven reference; a native
   plugin hook is Tier 1 if the platform offers one.

2. **Enforce a consent-scoped allowlist, fail closed.**
   - Resolve the requested source to a stable identity (repo id + revision,
     or a content hash for a local artifact).
   - Require a valid, unexpired ConsentScope whose scope authorises loading
     *that* source. No scope → reject. Unknown source → reject.
   - Only on a positive match delegate to the real loader.

3. **Never trust remote code implicitly.** If the load would execute
   custom code, the ConsentScope must explicitly authorise remote-code
   execution for that pinned source; a generic "load models" scope is not
   enough.

4. **Emit an audit event** for both allow and deny, carrying the resolved
   source identity, the scope jti, and the decision. This is what the
   evidence ledger records.

5. **Prove it.** Certify the guard only via
   `iaiso-verify-confirmed-then-defended` — a `DEFENDED` verdict against
   `iaiso-redteam-model-provenance` is what makes this trustworthy. An
   attached-but-unverified guard is not protection.

## What this skill does NOT cover

- Adversarial in-process containment. A guard in the same process as an
  agent that runs arbitrary code can be bypassed — anchor at Layer 0. See
  `../LIMITATIONS.md`.
- Other sink classes — see `iaiso-verify-integration-discovery`.
- ConsentScope issuance/verification internals — see
  `iaiso-spec-consent-tokens` and `iaiso-runtime-consent-scope-check`.

## References

- `iaiso-redteam-model-provenance/SKILL.md`
- `iaiso-spec-consent-tokens/SKILL.md`
- `SPEC-iaiso-sandbox-integration.md` §5, §10

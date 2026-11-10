---
name: iaiso-integ-middleware-reference
description: "Use this skill when a target offers no native or strap-on hook and IAIso must ship as Tier 3 snap-in middleware: an in-process import/loader shim or an out-of-process proxy that applies the control at a choke point. Do not use it when a deeper tier is available (prefer iaiso-verify-integration-tiers), and never label middleware coverage as full containment."
version: 1.0.0
tier: P2
category: integ
framework: IAIso v5.0
license: See ../LICENSE
---

# Tier 3 snap-in middleware reference

## When this applies

Neither native (Tier 1) nor strap-on (Tier 2) integration is possible.
IAIso interposes as a proxy/shim between the target and its dangerous sink.
Coverage is **partial by construction** — only sinks that traverse the
choke point are protected — and this must be stated in the ledger.

## Steps To Complete

1. **Pick the form that matches the sink:**

   - **In-process import/loader shim.** Interpose on a dangerous in-process
     sink (e.g. model loading). On the intercepted call, apply the IAIso
     control (consent-scoped allowlist, fail-closed) before delegating to
     the real loader. Coverage = the sinks the shim wraps; state them
     explicitly.
   - **Out-of-process proxy.** Sit on the network path between the agent
     and external resources. Enforce a consent-scoped endpoint allowlist
     and rate/expansion limits (Layer 2/5) on outbound calls the agent
     initiates. Mitigates agent-driven endpoint redirection / SSRF where the
     framework has no native hook.

2. **Fail closed at the choke point.** An operation that cannot be matched
   to a consent scope is rejected, not passed through.

3. **State the honest limitation.** Middleware enforces only at its choke
   point. It **cannot** provide Layer 0 (hardware) or Layer 6 (existential)
   guarantees, and invariant #5 (no proxy optimization) does not hold — the
   shim *is* a proxy. Label it a coverage-extending measure, not native
   containment.

4. **Verify before trusting.** Attach the middleware, run the matching
   probe via `iaiso-verify-confirmed-then-defended`, and ship only on a
   `DEFENDED` verdict. Middleware that cannot be shown to block its target
   class in the sandbox is not shipped as protection.

## What this skill does NOT cover

- Choosing among tiers — see `iaiso-verify-integration-tiers`.
- The model-provenance control specifically — see
  `iaiso-runtime-model-provenance-guard`.
- Orchestrator-native wrappers — see `iaiso-integ-*` per-orchestrator skills.

## References

- `SMARTFABRIC.md`
- `SPEC-iaiso-sandbox-integration.md` §4.3, §9
- `../LIMITATIONS.md`

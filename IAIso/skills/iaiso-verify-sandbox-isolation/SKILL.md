---
name: iaiso-verify-sandbox-isolation
description: "Use this skill to configure the SmartFabric container substrate correctly: network-isolated test phase (network=none) so a fired sentinel is provably local, plus bounded self-healing of missing dependencies. Do not use it to author probes (see iaiso-verify-confirmed-then-defended) or to weaken isolation for convenience."
version: 1.0.0
tier: P1
category: verify
framework: IAIso v5.0
license: See ../LICENSE
---

# SmartFabric sandbox isolation

## When this applies

Any SmartFabric run. Isolation is load-bearing: it is what makes a fired
sentinel *trustworthy* as evidence rather than ambiguous.

## Steps To Complete

1. **Two-phase network posture.**
   - **Build phase:** `network=bridge` is allowed (fetch toolchain/deps).
   - **Test phase:** `network=none` is REQUIRED. A sentinel that fires with
     no network is provably *local code execution*, not exfiltration.
   - Record the `network=none` attestation for the ledger.

2. **Per-target hardened image.** Provision a per-repo image; mount the
   cloned target read-only. Never mount host credentials into the test
   phase.

3. **Bounded self-healing dependencies.** Resolve missing Python deps
   automatically: known-map → LLM-fleet suggestion → module-name fallback.
   Bound the loop (cap retries) to avoid infinite install cycles. Log every
   self-healed package so the environment is reproducible.

4. **Fail honest on environment gaps.** If a dependency cannot be resolved
   or a loader cannot be exercised, the verifier verdict is `INCONCLUSIVE`,
   not "protected." Do not relax isolation to force a result.

5. **Closed-platform rule.** A closed platform is never cloned or probed
   against its live service. Build a local mediator that calls its
   documented API with supplied credentials, and verify only that local
   mediator inside this isolation. All adversarial testing stays inside the
   operator's own boundary.

## What this skill does NOT cover

- The two-pass verdict logic — see `iaiso-verify-confirmed-then-defended`.
- The ledger format — see `iaiso-verify-evidence-ledger`.
- Adversarial containment guarantees at runtime — see `../LIMITATIONS.md`;
  the sandbox isolates *verification*, and Layer 0 anchors isolate a live
  adversarial agent.

## References

- `SMARTFABRIC.md`
- `SPEC-iaiso-sandbox-integration.md` §0, §3, §6

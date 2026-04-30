---
name: iaiso-diagnose-vector-failure
description: "Use this skill when a conformance vector fails — in CI, in a port-in-progress, or after a spec bump. Do not use it for runtime divergence between two SDKs — those are likely real bugs, not vector failures."
version: 1.0.0
tier: P3
category: diagnostics
framework: IAIso v5.0
license: See ../LICENSE
---

# Diagnosing a conformance vector failure

## When this applies

`iaiso conformance run` reports `< 67/67`. A specific vector
fails.

## Steps To Complete

1. **Identify the subsystem.** The runner reports it.
   Triage order: pressure → consent → events → policy.
   Pressure failures cascade.

2. **Read the failing vector.** Each vector has `name`,
   `inputs`, and `expected`. Re-run the failing case in
   isolation.

3. **Apply the right tolerance.** Floats: `|impl - spec| ≤
   1e-9`. Bytes: bit-exact. Strings: equal. Misapplying
   tolerance is the most common false positive.

4. **For pressure vectors, check the threshold check
   order.** `release` BEFORE `escalation`. If your impl
   returns ESCALATED where the vector expects RELEASED on
   a value above release_threshold, that's the bug.

5. **For consent vectors, check claim presence and order.**
   The verifier rejects on missing claims; producers can
   drift in field order across reissues.

6. **For events vectors, check schema_version exact-equal
   to `"1.0"`.** A `1.0.0` produced where `"1.0"` is
   expected fails.

7. **For policy vectors, check the cross-field rules.**
   `release > escalation`, both in `[0,1]`.

## What this skill does NOT cover

- Authoring new vectors — that's a spec change, not a fix.

## References

- `core/spec/*/vectors.json`
- `core/docs/CONFORMANCE.md`

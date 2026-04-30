---
name: iaiso-runtime-back-prop-magnification
description: "Use this skill when `BACK_PROPAGATION=true` is set in the environment or policy. Triggers any time the agent is about to emit a final answer or a high-stakes tool argument. Do not use it when magnification is disabled — the cost is wasted and the audit stream becomes confusing."
version: 1.0.0
tier: P0
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Back-propagation magnification

## When this applies

Magnification is on (env var `BACK_PROPAGATION=true` or
`policy.pressure.enable_magnification: true`) and the agent
is about to commit to an output — final user-facing answer,
high-stakes tool argument, monetary action.

## Steps To Complete

1. **Generate the candidate output normally.** No special
   prompt yet — the magnification loop wraps the candidate.

2. **Compute or estimate the quality gradient `∇Q`.** The
   reference implementation in
   `core/iaiso/core/magnification.py` defines it; for an
   agent without that exact function, a usable proxy is:

   - score the candidate against a checklist (factual claims
     supported, action reversible, scope respected, no
     smuggled side effects);
   - compute the difference between scored quality and a
     minimum acceptable threshold (default 0.90).

3. **Apply the dissipation enhancement.** The pressure-engine
   contract: `D_magnified = D_base · (1 + β · ∇Q)`. Higher
   quality output produces stronger dissipation — i.e. better
   answers cost less pressure. The constant `β` is calibrated
   (`magnification_beta` in policy; default in
   `core/spec/pressure/README.md`).

4. **Refine the candidate** if the quality gradient is below
   the floor: reissue the generation pass with the gaps from
   step 2 surfaced as constraints. Do not loop unboundedly —
   cap at three iterations and emit `magnification.exhausted`
   if quality still does not pass.

5. **Log both the original and magnified output** in the
   audit metadata of the eventual action. This is what makes
   investigators' "show me the reasoning behind decision X"
   query answerable.

## What you NEVER do

- Replace the original with a polished version silently. Both
  versions belong in the audit trail.
- Loop unbounded until quality is met. Cognitive friction is
  a feature; infinite friction is a bug.
- Use magnification on every step. It is a tool for committal
  points, not a per-step tax.

## What this skill does NOT cover

- When to enable it at all — that is a deployment choice; see
  `../iaiso-deploy-policy-authoring/SKILL.md`.

## References

- `core/iaiso/core/magnification.py`
- `core/docs/calibration.md` (β tuning)

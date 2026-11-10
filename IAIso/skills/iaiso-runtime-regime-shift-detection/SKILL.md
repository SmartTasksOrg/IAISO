---
name: iaiso-runtime-regime-shift-detection
description: "Use this skill to implement Layer 3.5 — phase-transition monitoring. Triggers on planning-vs-execution regime shifts, drift detection, behaviour-change emission. Do not use it for ordinary step-to-step changes — those are not regime shifts."
version: 1.0.0
tier: P1
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Detecting and emitting regime shifts (Layer 3.5)

## When this applies

The agent transitions between qualitatively different
behaviour modes — planning → execution, exploration →
exploitation, idle → active. These transitions warrant their
own audit signal because they predict pressure spikes.

## Steps To Complete

1. **Define your regime states.** Common pairs:

   - `planning ↔ executing`
   - `exploration ↔ exploitation`
   - `idle ↔ active`
   - `single-agent ↔ delegating`

   Pick a small set per agent — three or fewer is normal.

2. **Pick a detection signal.** Reasonable defaults:

   - tool-call density (calls per minute) crossing a
     multiple of moving average;
   - planning-depth bursts (sustained `depth > 0` after a
     flat run);
   - the agent itself declaring the shift via a
     designated tool (`enter_phase`).

3. **Emit `regime.shift` audit events** with `from_phase`,
   `to_phase`, and the detection signal as `data`. Use a
   custom kind under your namespace
   (`mycorp.regime.shift`) so it does not collide with
   future IAIso kinds.

4. **Update calibration intent.** A planning-phase step
   weighs differently from an execution-phase step in some
   workloads — see `iaiso-deploy-calibration` for the
   multi-regime fitting pattern.

5. **Do not change pressure thresholds on regime shift.**
   The thresholds are policy, not behaviour. A regime shift
   informs the operator; it does not unilaterally change
   containment.

## What this skill does NOT cover

- Specific phase-transition detection algorithms — that is
  domain-specific.
- Layer 3 coordinator coupling — see
  `../iaiso-runtime-multi-agent-coordination/SKILL.md`.

## References

- `vision/docs/spec/02-framework-layers.md`

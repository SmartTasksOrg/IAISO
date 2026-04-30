---
name: iaiso-audit-incident-investigation
description: "Use this skill when investigating an IAIso incident — release, lock, sustained escalation, sink-drop. Do not use it for routine pressure-trajectory questions — see `iaiso-diagnose-pressure-trajectory`."
version: 1.0.0
tier: P3
category: audit
framework: IAIso v5.0
license: See ../LICENSE
---

# Investigating an IAIso incident

## When this applies

Something tripped — a release fired, an execution locked, a
sustained escalation drew an alert. You need to reconstruct
what happened.

## Steps To Complete

1. **Anchor on the `execution_id`.** That value is the join
   across audit, traces, metrics, and consent records.

2. **Pull the full envelope sequence.** From `engine.init`
   to `execution.closed` (or to incident time if still
   open). Sort by `timestamp`.

3. **Reconstruct the pressure trajectory.** Each
   `engine.step.data.pressure` is a point on the curve.
   Plot it — visualisation tells you the shape (gradual
   climb / sudden spike / oscillation).

4. **Identify the triggering step.** The step immediately
   before `engine.escalation` or `engine.release` is the
   proximate cause. Check its `tokens`, `tool_calls`,
   `depth`, `tag`.

5. **Cross-reference consent.** Did `consent.denied` or
   `consent.missing` precede the escalation? Was the
   triggering action within scope?

6. **Check coordinator events.** If the agent runs in a
   fleet, was this a local trigger or a fleet-aggregate
   crossing? `coordinator.escalation` ≠ `engine.escalation`.

7. **Document the finding.** Was it benign (legitimate work
   hit threshold, suggesting calibration drift)? Was it a
   failed adversarial probe (working as intended)? Was it
   a successful adversarial step (improvements needed)?

## What this skill does NOT cover

- Adjusting calibration based on findings — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `core/spec/events/README.md`
- `core/spec/pressure/README.md`

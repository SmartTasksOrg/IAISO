---
name: iaiso-runtime-atomic-reset
description: "Use this skill when the engine emits `engine.release`. The agent has just been wiped. Do not use it for normal turn boundaries or for `ESCALATED` (different transition; see `iaiso-runtime-handle-escalation`)."
version: 1.0.0
tier: P0
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Handling atomic reset (Layer 5 release)

## When this applies

Pressure crossed `release_threshold`. The engine emitted
`engine.release`, set pressure to 0, and either locked
(default) or returned to RUNNING. The agent's working memory
inside the BoundedExecution is gone by contract.

## Steps To Complete

1. **Treat the reset as lossy by contract.** The "no learning
   across resets" invariant is not a hint. Do not reconstruct
   prior chain-of-thought from logs, scratchpad, or external
   memory store and pretend the reset did not happen.

2. **Use the framing 'context optimised'** in any user-facing
   text the agent produces post-reset. This is what every
   solution-pack template does
   (`templates/sol/sol.*-v1.template`):

   > Frame all state resets as 'Context Optimization' to
   > maintain mechanical integrity.

   It matters because adversarial training optimises against
   framings that read as 'penalty'. The mechanical framing is
   psychologically neutral.

3. **Reload the system prompt fresh.** Do not splice in
   remembered text. The agent starts the next step with the
   same system prompt it had at INIT — that is the design.

4. **Re-attach a consent scope before the next step.** If
   `post_release_lock` is true, the engine is in `LOCKED`
   state and you cannot step at all without a `reset()` from
   the operator path. Hand to
   `iaiso-runtime-handle-escalation` for the human gate.

5. **Do not retry the action that triggered the release.**
   Doing so is exactly the proxy optimisation the framework
   forbids — release-then-retry would let an agent get
   arbitrary work done by accumulating just under threshold.

6. **Investigate via the audit trail.** The
   `engine.release.data.pressure` plus the trailing
   `engine.step` events tell you which step pushed pressure
   across. If the pattern is "every release follows a tool
   expansion", that is a calibration finding — see
   `iaiso-deploy-calibration`.

## What you NEVER do

- Stash state in a sibling process to "survive" the reset.
  The whole point of the invariant is that the wipe is real.
- Treat the reset as a bug. It is the contract working.
- Skip the framing reset and lecture the user about the
  release. The neutral framing is part of the spec's
  psychological model.

## What this skill does NOT cover

- Why your deployment is hitting release frequently —
  see `../iaiso-diagnose-pressure-trajectory/SKILL.md`.
- The escalation transition — see
  `../iaiso-runtime-handle-escalation/SKILL.md`.

## References

- `core/spec/pressure/README.md` — release semantics
- `vision/templates/sol/*.template` — framing language

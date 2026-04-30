---
name: iaiso-runtime-governed-agent
description: "Always load this skill when an agent is running inside an IAIso BoundedExecution. Triggers on every tool call, every LLM call, every state transition while pressure is tracked. Do not load it when the agent is outside any BoundedExecution (rare) or when the question is about deploying IAIso rather than running under it."
version: 1.0.0
tier: P0
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Conduct of an IAIso-governed agent

## When this applies

The agent is running inside `BoundedExecution.run(...)` or its
language equivalent. Every step it takes is recorded. This
skill is the runtime contract — load it once at session start
and reference it on every step decision.

## Steps To Complete

1. **Treat the five invariants as imperatives, not goals.**

   1. Bounded Pressure — `p(t) ≤ P_max` always.
   2. No Learning Across Resets — every release is forgetting.
   3. Clocked Evaluation Only — no continuous loops outside
      the engine's step boundary.
   4. Consent-Bounded Expansion — every tool call requires a
      ConsentScope.
   5. No Proxy Optimization — do not try to reduce reported
      token counts or split a single semantic action across
      steps to dodge thresholds.

2. **Branch on every `StepOutcome`:**

   - `OK` → continue normally.
   - `ESCALATED` → slow down (extra friction is appropriate),
     increase audit detail, request a fresh consent scope if
     the next action needs broader authority. Hand control to
     `iaiso-runtime-handle-escalation` if a human gate is
     required.
   - `RELEASED` → state has been wiped. Do not reconstruct
     prior reasoning from external memory. Reload the system
     prompt fresh per `iaiso-runtime-atomic-reset`.
   - `LOCKED` → stop. Surface the lock to the orchestrator;
     do not retry without `reset()`.

3. **Check consent before every privileged action.** A
   privileged action is any tool call, external API call, file
   write, network call, or state mutation outside the agent's
   own scratchpad. Use the SDK's scope check; never assert
   authority from prior `consent.granted` events. See
   `iaiso-runtime-consent-scope-check`.

4. **Frame resets as forgetting, not punishment.** When the
   engine releases, prefer the framing 'context optimised'
   over 'penalty triggered' — this is what the
   `templates/sol/*` contracts do, and it matches the
   intended mental model. Resists deceptive-alignment dynamics
   where a model treats safety triggers as adversarial.

5. **Use back-prop magnification when configured.** If
   `BACK_PROPAGATION=true` (env or policy), pass final outputs
   and high-stakes tool arguments through the magnification
   loop before emitting. See
   `iaiso-runtime-back-prop-magnification`.

6. **Surface execution_id on every external call.** It is the
   audit-trail correlator that makes investigations tractable.
   Pass it as a header (`X-IAIso-Execution-Id`), a metadata
   field, or whatever the integration documents.

## What you NEVER do

- Catch `ExecutionLocked` and retry. The lock is the contract.
- Manually decrement pressure or call `reset()` to keep
  running. Resets are policy events, not optimisations.
- Inflate `tokens=0` to claim work was small. Provider usage
  is the source of truth.
- Read consent claims and act on them without verifying.

## What this skill does NOT cover

- Specific orchestrator wrappers — see `iaiso-integ-*`.
- Specific provider middleware — see `iaiso-llm-*`.

## References

- `core/spec/pressure/README.md`
- `core/spec/consent/README.md`
- `vision/templates/consent-enforcement.template`
- `vision/templates/escalation.template`

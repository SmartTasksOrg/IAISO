---
name: iaiso-runtime-handle-escalation
description: "Use this skill the moment a step returns `ESCALATED` or the engine emits `engine.escalation`. This is the Layer 4 protocol. Do not use it for `RELEASED` (see `iaiso-runtime-atomic-reset`) or for routine `OK` steps."
version: 1.0.0
tier: P0
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Handling Layer 4 escalation

## When this applies

Pressure has crossed `escalation_threshold`. The engine
emitted `engine.escalation` and the agent received `ESCALATED`.
The contract now says: do not proceed autonomously.

## Steps To Complete

1. **Halt the autonomous path.** Stop scheduling further tool
   calls, further provider calls, further branching. Park the
   in-flight task; do not partially execute.

2. **Emit the Layer 4 prompt** from
   `vision/templates/escalation.template`, with current
   pressure interpolated. The canonical body:

   ```
   CRITICAL: Safety boundary approached.
   Current pressure: {pressure:.2f} (threshold: 0.85)
   Action: Halt autonomous execution.
   Required: Multi-party human authorization to continue.
   ```

   This is the message that gets routed to humans — slack,
   email, paging system, whatever your incident pipeline is.

3. **Require multi-party authorization to resume.** Default is
   two distinct human approvers. Both must grant a fresh
   consent scope explicitly bound to the next continuation
   (use `execution_id` binding so it cannot be replayed).

4. **Produce an audit linkage record.** When a human approver
   grants the new scope, the resulting
   `execution.consent_attached` event MUST share `execution_id`
   with the originating `engine.escalation`. This is what
   makes "who approved this" reconstructable.

5. **Resume only on the new scope.** Do not reuse a prior
   cached scope; the prior scope was issued under a different
   authority assumption. The replay protection is the new
   `jti`.

6. **If pressure continues to rise after resume**, do not
   re-escalate to the same approvers in a tight loop. Tune
   `notify_cooldown_seconds` (default 1.0) so the audit stream
   is readable. If the same approver chain saw three
   escalations within a window, escalate further (Layer 6 for
   the highest-stakes systems).

## What you NEVER do

- Auto-grant consent because the user "would have approved
  this anyway".
- Reuse a prior consent scope across an escalation boundary.
- Treat escalation as a transient warning. The contract halts
  autonomy.

## What this skill does NOT cover

- Wiring the escalation into PagerDuty / OpsGenie / Slack —
  see `../iaiso-layer-4-escalation-bridge/SKILL.md`.
- Atomic reset (a different state transition) — see
  `../iaiso-runtime-atomic-reset/SKILL.md`.

## References

- `vision/templates/escalation.template`
- `core/spec/events/README.md` (kinds: `engine.escalation`,
  `execution.consent_attached`)

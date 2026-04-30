---
name: iaiso-runtime-multi-agent-coordination
description: "Use this skill when an agent participates in a coordinator-managed fleet (Layer 3). Triggers on shared pressure, fleet-wide escalation, multi-process agent runs. Do not use it for single-agent operation."
version: 1.0.0
tier: P1
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Conduct of an agent inside a coordinated fleet

## When this applies

The agent runs alongside other agents under a shared
coordinator. Fleet pressure can escalate independently of
local pressure.

## Steps To Complete

1. **Register at start.** The SDK does this when the
   coordinator is configured; the resulting
   `coordinator.execution_registered` event records the
   agent's join.

2. **Update on every step.** The pressure engine pushes the
   local pressure into the coordinator's hash atomically.
   Do not push manually — the path is the Lua script, not
   client-side HSET.

3. **React to coordinator events differently from engine
   events.**

   - `engine.escalation` is YOUR pressure crossing.
   - `coordinator.escalation` is FLEET aggregate crossing —
     your local pressure may be fine. The reaction is still
     to slow down (other agents are stressed and your local
     work is part of the fleet load).

4. **Implement an `on_coordinator_escalation` callback** that
   at minimum: reduces the rate of new tool calls, increases
   audit detail, and emits a distinguishing log line. Do
   not auto-reset on coordinator escalation; the contract is
   backpressure, not failure.

5. **Unregister on clean shutdown.** This trims your
   contribution from the aggregate immediately, instead of
   waiting for TTL. It also writes
   `coordinator.execution_unregistered` to audit.

6. **Do not rely on per-process callback fanout for
   fleet-wide semantics.** Each process fires its own
   callback; for "every worker reacts to the same
   transition", subscribe to the audit stream.

## What you NEVER do

- Spoof another execution's pressure (HSET fields you do not
  own). The Lua script does not enforce field ownership at
  Redis level — your operational discipline does.
- Treat coordinator events as ground truth for local
  decisions; they are fleet signals, not local outcomes.

## What this skill does NOT cover

- Coordinator protocol — see
  `../iaiso-spec-coordinator-protocol/SKILL.md`.
- Coordinator deployment — see
  `../iaiso-deploy-coordinator-redis/SKILL.md`.

## References

- `core/spec/coordinator/README.md` §2 emitted events

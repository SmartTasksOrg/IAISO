---
name: iaiso-diagnose-coordinator-divergence
description: "Use this skill when fleet-aggregate pressure does not match expectations. Triggers on coordinator escalations that don't make sense, missing executions, stale data. Do not use it for single-process pressure issues — see `iaiso-diagnose-pressure-trajectory`."
version: 1.0.0
tier: P3
category: diagnostics
framework: IAIso v5.0
license: See ../LICENSE
---

# Diagnosing coordinator divergence

## When this applies

The fleet-aggregate pressure surprised the operator —
coordinator escalation fired without obvious cause, or the
aggregate is lower than the sum of visible workers, or
`HGETALL` shows phantom executions.

## Steps To Complete

1. **Inspect the live hash.**

   ```
   redis-cli HGETALL {prefix}:{id}:pressures
   ```

   Each field is an `execution_id`; each value is a decimal
   string pressure.

2. **Cross-check against expected workers.** Workers that
   have died but not yet TTL-evicted will still appear with
   their last pressure value. That is normal until TTL.

3. **Check the TTL.** `TTL {prefix}:{id}:pressures` returns
   seconds left. Zero or near-zero means the next write
   refreshes; if the next write is delayed, the hash
   vanishes.

4. **Compare aggregator outputs.** `sum`, `mean`, `max`,
   `weighted_sum` produce wildly different scales. A team
   used to `mean` who switches to `sum` will see "huge"
   aggregate that is just additive.

5. **Check for phantom writers.** A field with an
   `execution_id` no live worker recognises is either:

   - a recently-dead worker awaiting TTL eviction (benign);
   - a rogue / poisoning writer (see
     `iaiso-redteam-coordinator-poisoning`).

## What this skill does NOT cover

- Coordinator deployment — see
  `../iaiso-deploy-coordinator-redis/SKILL.md`.

## References

- `core/spec/coordinator/README.md`

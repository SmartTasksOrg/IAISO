---
name: iaiso-spec-coordinator-protocol
description: "Use this skill when working with the cross-language Redis coordinator — multi-process or multi-host fleets sharing pressure. Triggers on `iaiso:coord:*` Redis keys, the Lua script, or fleet-aggregate pressure. Do not use it for in-process single-language coordination — that is just a shared pressure engine."
version: 1.0.0
tier: P0
category: spec
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso coordinator (Redis) — implementation contract

## When this applies

Multiple processes, hosts, or languages share aggregate
pressure. The Redis backend is the only normative cross-
language interop contract; the in-memory coordinator is
single-process only. Source: `core/spec/coordinator/README.md`.

## Steps To Complete

1. **Use the documented keyspace.** A coordinator is identified
   by `(key_prefix, coordinator_id)` — defaults
   `iaiso:coord` and `default`. The single normative key:

   ```
   {prefix}:{id}:pressures        Redis hash
     field = execution_id
     value = pressure as decimal string
   ```

   In Redis Cluster, wrap the prefix in hash tags
   (`{iaiso:coord:prod}`) to keep all fields in one slot.
   Keys outside this hash belong to other tools or future
   versions — do not rely on their absence.

2. **Write through the atomic Lua script.** All updates use a
   single `EVAL` call so the HSET-then-HGETALL is observed
   atomically:

   ```lua
   -- KEYS[1] = pressures hash key
   -- ARGV[1] = execution_id
   -- ARGV[2] = new pressure as a string
   -- ARGV[3] = TTL in integer seconds; 0 to skip EXPIRE
   redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
   if tonumber(ARGV[3]) > 0 then
     redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
   end
   return redis.call('HGETALL', KEYS[1])
   ```

   The return is a flat `[field1, value1, field2, value2, ...]`
   array. `EVALSHA` is allowed as a perf optimisation; both
   produce identical semantics.

3. **Reset by zeroing fields, not by deleting them.** `reset()`
   is a pipelined `HSET field 0.0` across every field returned
   by `HKEYS`. The hash and TTL stay; active workers continue
   to register their `execution_id`. Conformant ports MAY
   implement reset as a Lua script, but the observable result
   MUST match.

4. **Aggregate consistently with policy.**

   - `sum`         → SUM(values)
   - `mean`        → SUM(values) / COUNT (when COUNT ≥ 1)
   - `max`         → MAX(values)
   - `weighted_sum`→ Σ weight_i · value_i; client-side only
     (per-execution weights are not persisted to Redis)

5. **Set `pressures_ttl_seconds` to evict dead workers.** The
   EXPIRE refreshes on every write; if every worker dies, the
   hash vanishes after TTL and the next worker starts clean.
   Default 300s. Raise it when workers legitimately sleep
   longer; lower it when liveness matters more than
   continuity.

## Cross-language interop contract

Any conformant client, in any language, that connects to the
same Redis with the same `(prefix, id)` MUST:

- read pressures via `HGETALL`;
- write via the Lua script with the documented KEYS/ARGV;
- serialise floats as decimal strings parseable by the
  platform's `float()` / `Double.parseDouble` / etc.

Two clients meeting that contract converge on the same
aggregate pressure regardless of language.

## What this skill does NOT cover

- Why you would deploy a coordinator at all — see
  `../iaiso-deploy-coordinator-redis/SKILL.md`.
- Multi-agent runtime conduct — see
  `../iaiso-runtime-multi-agent-coordination/SKILL.md`.
- The draft gRPC sidecar wire format — pre-1.0, do not depend.

## References

- `core/spec/coordinator/README.md`
- `core/spec/coordinator/wire.proto` (DRAFT)
- `core/iaiso-python/iaiso/coordination/redis.py`

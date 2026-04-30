---
name: iaiso-deploy-coordinator-redis
description: "Use this skill when running IAIso across more than one process or host. Triggers on multi-worker deployment, Redis topology, fleet-aggregate pressure. Do not use it for single-process deployments — they need no coordinator."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Deploying the IAIso Redis coordinator

## When this applies

The deployment has more than one IAIso process — multiple
workers, multiple hosts, or multiple languages — that should
share aggregate pressure.

## Steps To Complete

1. **Pick Redis topology.** Single-instance is fine for
   dev; replicated (sentinel) for prod; cluster for very
   large fleets. The Lua script uses one key, so any
   topology works.

2. **Choose `(key_prefix, coordinator_id)`.** Default:
   `iaiso:coord` and `default`. For environment isolation:

   ```
   key_prefix = "iaiso:coord:prod"     # explicit env
   coordinator_id = "agents"           # logical fleet
   ```

   In Redis Cluster, wrap the prefix in hash tags
   (`{iaiso:coord:prod}`) to keep all of a fleet's keys in
   one slot.

3. **Set `pressures_ttl_seconds`.** Default 300. Raise it
   if your workers legitimately sleep longer; lower it if
   liveness matters more than continuity.

4. **Configure aggregator and thresholds in policy.** See
   `iaiso-spec-policy-files §4`. Aggregator choice
   changes the threshold scale:

   - `sum`         → typical thresholds 5.0 / 8.0
   - `mean`        → typical thresholds 0.85 / 0.95
   - `max`         → typical thresholds 0.85 / 0.95
   - `weighted_sum`→ thresholds depend on weight magnitudes

5. **Wire callbacks.** When aggregate fleet pressure hits
   escalation, the coordinator emits
   `coordinator.escalation`. Each process observing the
   transition fires its local `on_escalation` callback. For
   fleet-wide reaction, subscribe through the audit stream
   (it is the authoritative global signal).

6. **Test failure modes.** Kill a worker; confirm its
   contribution evicts after TTL. Partition the network;
   confirm aggregate degrades gracefully (clients read what
   they can see). Restart Redis; confirm fields are zeroed
   not deleted by `reset()`.

## What this skill does NOT cover

- Wire-format details of the coordinator — see
  `../iaiso-spec-coordinator-protocol/SKILL.md`.
- Multi-agent runtime behaviour — see
  `../iaiso-runtime-multi-agent-coordination/SKILL.md`.

## References

- `core/spec/coordinator/README.md`
- `core/iaiso-python/iaiso/coordination/redis.py`
- `known-limitations.md` — distributed-coordination architecture

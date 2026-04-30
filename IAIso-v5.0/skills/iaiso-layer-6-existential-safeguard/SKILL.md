---
name: iaiso-layer-6-existential-safeguard
description: "Use this skill only for high-stakes deployments needing Layer 6 — singleton prevention, replication caps, global halt. Do not use it for ordinary internal tooling; most deployments are fine without Layer 6."
version: 1.0.0
tier: P1
category: layer
framework: IAIso v5.0
license: See ../LICENSE
---

# Implementing Layer 6 existential safeguards

## When this applies

The deployment is in a category where uncontrolled spread
or replication of agent state would be catastrophic — gene
editing, autonomous weapons, large-scale infrastructure.
Most deployments are not in this category. If yours is not,
skip Layer 6.

## Steps To Complete

1. **Decide what "singleton" means for the deployment.** A
   common reading: only one BoundedExecution with this
   `system_id` is allowed to exist globally at any time.
   Implement via a distributed lock (Redis SETNX with TTL,
   etcd lease, ZooKeeper ephemeral node).

2. **Implement replication caps.** If the agent can spawn
   sub-agents, cap the count at the source. Coordinator
   aggregate pressure with `aggregator: max` and a low
   threshold can serve double duty.

3. **Wire a global halt capability.** A single audited
   command that flips all running BoundedExecutions to
   `LOCKED` simultaneously. Implement as a coordinator
   broadcast that every execution polls and obeys.

4. **Air-gap state where domain demands it.** The
   `sol.bio.genomics-v1` reference design air-gaps gene-
   edit simulations on dedicated hardware. The IAIso
   framework supports the audit and consent layers; the
   air-gap itself is a Layer 0 deployment choice.

5. **Test the halt.** A Layer 6 mechanism untested is a
   Layer 6 mechanism that does not work. Run a quarterly
   drill: invoke halt, confirm every execution acknowledges
   within seconds, document the audit trail.

6. **Bind activation to a strong human gate.** Layer 6 is
   not auto-fired. Multi-party authorisation by senior
   authority, with a kill-switch that a Layer 4 escalation
   cannot trigger by itself.

## What this skill does NOT cover

- When Layer 6 is justified — talk to your security and
  compliance teams. Most deployments do not need it.
- Layer 4 — see
  `../iaiso-layer-4-escalation-bridge/SKILL.md`.

## References

- `vision/docs/spec/06-layers.md`
- `vision/components/sol/sol.bio.genomics-v1.json`

---
name: iaiso-system-redis
description: "Use this skill when building or reviewing an IAIso integration with Redis (category: database). Triggers on `Redis`, `database.redis`, or any agent action that reads from or writes to Redis. Do not use this skill for unrelated database systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Redis integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Redis,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Redis system template** as the starting point:

   ```
   vision/templates/systems/redis.template
   vision/systems/database/redis/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Redis the
   convention is `database.redis`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `database.redis.read`, `database.redis.write`, or
   `database.redis.admin.delete`.

3. **Map Redis's operations to step inputs.** Key reads → `tool_calls`; key writes → writes; FLUSHDB / CONFIG → Layer 4 escalation.

4. **Wire Redis's authentication into IAIso's identity bridge.**
   If Redis fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Redis integration and confirm pressure stays
   under `escalation_threshold`; run a stress workload and
   confirm it crosses cleanly.

## What this skill does NOT cover

- The wire-format contract for consent scopes — see
  `../iaiso-spec-consent-tokens/SKILL.md`.
- Audit emission specifics — see
  `../iaiso-spec-audit-events/SKILL.md`.
- General runtime conduct — see
  `../iaiso-runtime-governed-agent/SKILL.md`.

## References

- `vision/systems/database/redis/README.md`
- `vision/templates/systems/redis.template`
- `vision/systems/INDEX.md`

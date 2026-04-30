---
name: iaiso-system-postgresql
description: "Use this skill when building or reviewing an IAIso integration with PostgreSQL (category: database). Triggers on `PostgreSQL`, `database.postgresql`, or any agent action that reads from or writes to PostgreSQL. Do not use this skill for unrelated database systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# PostgreSQL integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to PostgreSQL,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the PostgreSQL system template** as the starting point:

   ```
   vision/templates/systems/postgresql.template
   vision/systems/database/postgresql/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For PostgreSQL the
   convention is `database.postgresql`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `database.postgresql.read`, `database.postgresql.write`, or
   `database.postgresql.admin.delete`.

3. **Map PostgreSQL's operations to step inputs.** SELECT → `tool_calls`; DML → writes; DDL and `pg_*` admin functions → broadest scope.

4. **Wire PostgreSQL's authentication into IAIso's identity bridge.**
   If PostgreSQL fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the PostgreSQL integration and confirm pressure stays
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

- `vision/systems/database/postgresql/README.md`
- `vision/templates/systems/postgresql.template`
- `vision/systems/INDEX.md`

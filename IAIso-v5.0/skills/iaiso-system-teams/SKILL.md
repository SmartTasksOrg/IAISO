---
name: iaiso-system-teams
description: "Use this skill when building or reviewing an IAIso integration with Microsoft Teams (category: collaboration). Triggers on `Microsoft Teams`, `collab.teams`, or any agent action that reads from or writes to Microsoft Teams. Do not use this skill for unrelated collaboration systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Microsoft Teams integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Microsoft Teams,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Microsoft Teams system template** as the starting point:

   ```
   vision/templates/systems/teams.template
   vision/systems/collaboration/teams/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Microsoft Teams the
   convention is `collab.teams`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `collab.teams.read`, `collab.teams.write`, or
   `collab.teams.admin.delete`.

3. **Map Microsoft Teams's operations to step inputs.** Reading messages → reads; posting → writes; tenant-admin actions → Layer 4 escalation.

4. **Wire Microsoft Teams's authentication into IAIso's identity bridge.**
   If Microsoft Teams fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Microsoft Teams integration and confirm pressure stays
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

- `vision/systems/collaboration/teams/README.md`
- `vision/templates/systems/teams.template`
- `vision/systems/INDEX.md`

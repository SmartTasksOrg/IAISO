---
name: iaiso-system-ping
description: "Use this skill when building or reviewing an IAIso integration with Ping Identity (category: identity). Triggers on `Ping Identity`, `identity.ping`, or any agent action that reads from or writes to Ping Identity. Do not use this skill for unrelated identity systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Ping Identity integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Ping Identity,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Ping Identity system template** as the starting point:

   ```
   vision/templates/systems/ping.template
   vision/systems/identity/ping/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Ping Identity the
   convention is `identity.ping`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `identity.ping.read`, `identity.ping.write`, or
   `identity.ping.admin.delete`.

3. **Map Ping Identity's operations to step inputs.** Application config reads vs writes is the primary scope split; policy edits trigger Layer 4 escalation in regulated deployments.

4. **Wire Ping Identity's authentication into IAIso's identity bridge.**
   If Ping Identity fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Ping Identity integration and confirm pressure stays
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

- `vision/systems/identity/ping/README.md`
- `vision/templates/systems/ping.template`
- `vision/systems/INDEX.md`

---
name: iaiso-system-zoom
description: "Use this skill when building or reviewing an IAIso integration with Zoom (category: collaboration). Triggers on `Zoom`, `collab.zoom`, or any agent action that reads from or writes to Zoom. Do not use this skill for unrelated collaboration systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Zoom integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Zoom,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Zoom system template** as the starting point:

   ```
   vision/templates/systems/zoom.template
   vision/systems/collaboration/zoom/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Zoom the
   convention is `collab.zoom`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `collab.zoom.read`, `collab.zoom.write`, or
   `collab.zoom.admin.delete`.

3. **Map Zoom's operations to step inputs.** Meeting reads → `tool_calls`; recording downloads → writes (cost and PII implications).

4. **Wire Zoom's authentication into IAIso's identity bridge.**
   If Zoom fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Zoom integration and confirm pressure stays
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

- `vision/systems/collaboration/zoom/README.md`
- `vision/templates/systems/zoom.template`
- `vision/systems/INDEX.md`

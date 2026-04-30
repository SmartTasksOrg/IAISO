---
name: iaiso-system-amd
description: "Use this skill when building or reviewing an IAIso integration with AMD (category: hardware). Triggers on `AMD`, `hardware.amd`, or any agent action that reads from or writes to AMD. Do not use this skill for unrelated hardware systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# AMD integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to AMD,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the AMD system template** as the starting point:

   ```
   vision/templates/systems/amd.template
   vision/systems/hardware/amd/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For AMD the
   convention is `hardware.amd`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `hardware.amd.read`, `hardware.amd.write`, or
   `hardware.amd.admin.delete`.

3. **Map AMD's operations to step inputs.** MCA event reads → `tool_calls`; SEV VM lifecycle changes → writes.

4. **Wire AMD's authentication into IAIso's identity bridge.**
   If AMD fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the AMD integration and confirm pressure stays
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

- `vision/systems/hardware/amd/README.md`
- `vision/templates/systems/amd.template`
- `vision/systems/INDEX.md`

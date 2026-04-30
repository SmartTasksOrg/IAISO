---
name: iaiso-system-workday
description: "Use this skill when building or reviewing an IAIso integration with Workday (category: erp). Triggers on `Workday`, `erp.workday`, or any agent action that reads from or writes to Workday. Do not use this skill for unrelated erp systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Workday integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Workday,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Workday system template** as the starting point:

   ```
   vision/templates/systems/workday.template
   vision/systems/erp/workday/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Workday the
   convention is `erp.workday`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `erp.workday.read`, `erp.workday.write`, or
   `erp.workday.admin.delete`.

3. **Map Workday's operations to step inputs.** Worker / job-data reads → `tool_calls`; comp / payroll changes → writes with Layer 4 escalation.

4. **Wire Workday's authentication into IAIso's identity bridge.**
   If Workday fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Workday integration and confirm pressure stays
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

- `vision/systems/erp/workday/README.md`
- `vision/templates/systems/workday.template`
- `vision/systems/INDEX.md`

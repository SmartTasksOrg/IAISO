---
name: iaiso-system-dynamics365
description: "Use this skill when building or reviewing an IAIso integration with Dynamics 365 (category: crm). Triggers on `Dynamics 365`, `crm.dynamics365`, or any agent action that reads from or writes to Dynamics 365. Do not use this skill for unrelated crm systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Dynamics 365 integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Dynamics 365,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Dynamics 365 system template** as the starting point:

   ```
   vision/templates/systems/dynamics365.template
   vision/systems/crm/dynamics365/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Dynamics 365 the
   convention is `crm.dynamics365`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `crm.dynamics365.read`, `crm.dynamics365.write`, or
   `crm.dynamics365.admin.delete`.

3. **Map Dynamics 365's operations to step inputs.** FetchXML queries → `tool_calls`; entity updates → writes. Power Automate flows triggered by the agent count as additional `tool_calls`.

4. **Wire Dynamics 365's authentication into IAIso's identity bridge.**
   If Dynamics 365 fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Dynamics 365 integration and confirm pressure stays
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

- `vision/systems/crm/dynamics365/README.md`
- `vision/templates/systems/dynamics365.template`
- `vision/systems/INDEX.md`

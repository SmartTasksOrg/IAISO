---
name: iaiso-system-hubspot
description: "Use this skill when building or reviewing an IAIso integration with HubSpot (category: crm). Triggers on `HubSpot`, `crm.hubspot`, or any agent action that reads from or writes to HubSpot. Do not use this skill for unrelated crm systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# HubSpot integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to HubSpot,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the HubSpot system template** as the starting point:

   ```
   vision/templates/systems/hubspot.template
   vision/systems/crm/hubspot/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For HubSpot the
   convention is `crm.hubspot`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `crm.hubspot.read`, `crm.hubspot.write`, or
   `crm.hubspot.admin.delete`.

3. **Map HubSpot's operations to step inputs.** Contact searches → reads; workflow / sequence edits → writes; bulk updates need `crm.hubspot.bulk` and broader approval.

4. **Wire HubSpot's authentication into IAIso's identity bridge.**
   If HubSpot fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the HubSpot integration and confirm pressure stays
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

- `vision/systems/crm/hubspot/README.md`
- `vision/templates/systems/hubspot.template`
- `vision/systems/INDEX.md`

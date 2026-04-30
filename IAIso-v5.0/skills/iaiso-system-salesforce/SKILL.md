---
name: iaiso-system-salesforce
description: "Use this skill when building or reviewing an IAIso integration with Salesforce (category: crm). Triggers on `Salesforce`, `crm.salesforce`, or any agent action that reads from or writes to Salesforce. Do not use this skill for unrelated crm systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Salesforce integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Salesforce,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Salesforce system template** as the starting point:

   ```
   vision/templates/systems/salesforce.template
   vision/systems/crm/salesforce/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Salesforce the
   convention is `crm.salesforce`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `crm.salesforce.read`, `crm.salesforce.write`, or
   `crm.salesforce.admin.delete`.

3. **Map Salesforce's operations to step inputs.** SOQL queries → `tool_calls`; record updates → writes. API-call limits make `tool_coefficient` worth tuning higher than default.

4. **Wire Salesforce's authentication into IAIso's identity bridge.**
   If Salesforce fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Salesforce integration and confirm pressure stays
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

- `vision/systems/crm/salesforce/README.md`
- `vision/templates/systems/salesforce.template`
- `vision/systems/INDEX.md`

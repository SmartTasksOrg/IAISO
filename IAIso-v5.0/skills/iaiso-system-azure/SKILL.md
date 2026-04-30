---
name: iaiso-system-azure
description: "Use this skill when building or reviewing an IAIso integration with Azure (category: cloud). Triggers on `Azure`, `cloud.azure`, or any agent action that reads from or writes to Azure. Do not use this skill for unrelated cloud systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Azure integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Azure,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Azure system template** as the starting point:

   ```
   vision/templates/systems/azure.template
   vision/systems/cloud/azure/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Azure the
   convention is `cloud.azure`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `cloud.azure.read`, `cloud.azure.write`, or
   `cloud.azure.admin.delete`.

3. **Map Azure's operations to step inputs.** Resource Manager reads → `tool_calls`; deployments → writes; RBAC role assignments → broadest scope.

4. **Wire Azure's authentication into IAIso's identity bridge.**
   If Azure fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Azure integration and confirm pressure stays
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

- `vision/systems/cloud/azure/README.md`
- `vision/templates/systems/azure.template`
- `vision/systems/INDEX.md`

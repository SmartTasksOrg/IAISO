---
name: iaiso-system-sap
description: "Use this skill when building or reviewing an IAIso integration with SAP (category: erp). Triggers on `SAP`, `erp.sap`, or any agent action that reads from or writes to SAP. Do not use this skill for unrelated erp systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# SAP integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to SAP,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the SAP system template** as the starting point:

   ```
   vision/templates/systems/sap.template
   vision/systems/erp/sap/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For SAP the
   convention is `erp.sap`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `erp.sap.read`, `erp.sap.write`, or
   `erp.sap.admin.delete`.

3. **Map SAP's operations to step inputs.** BAPI / OData reads → `tool_calls`; financial postings → writes with mandatory Layer 4 escalation for amounts > threshold.

4. **Wire SAP's authentication into IAIso's identity bridge.**
   If SAP fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the SAP integration and confirm pressure stays
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

- `vision/systems/erp/sap/README.md`
- `vision/templates/systems/sap.template`
- `vision/systems/INDEX.md`

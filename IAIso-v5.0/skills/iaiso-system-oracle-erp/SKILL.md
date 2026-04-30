---
name: iaiso-system-oracle-erp
description: "Use this skill when building or reviewing an IAIso integration with Oracle ERP (category: erp). Triggers on `Oracle ERP`, `erp.oracle`, or any agent action that reads from or writes to Oracle ERP. Do not use this skill for unrelated erp systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Oracle ERP integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Oracle ERP,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Oracle ERP system template** as the starting point:

   ```
   vision/templates/systems/erp.template
   vision/systems/erp/erp/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Oracle ERP the
   convention is `erp.oracle`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `erp.oracle.read`, `erp.oracle.write`, or
   `erp.oracle.admin.delete`.

3. **Map Oracle ERP's operations to step inputs.** Reports → reads; PO / invoice modifications → writes with segregation-of-duties scope splits.

4. **Wire Oracle ERP's authentication into IAIso's identity bridge.**
   If Oracle ERP fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Oracle ERP integration and confirm pressure stays
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

- `vision/systems/erp/erp/README.md`
- `vision/templates/systems/erp.template`
- `vision/systems/INDEX.md`

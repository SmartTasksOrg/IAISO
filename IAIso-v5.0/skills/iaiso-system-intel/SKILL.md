---
name: iaiso-system-intel
description: "Use this skill when building or reviewing an IAIso integration with Intel (category: hardware). Triggers on `Intel`, `hardware.intel`, or any agent action that reads from or writes to Intel. Do not use this skill for unrelated hardware systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Intel integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Intel,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Intel system template** as the starting point:

   ```
   vision/templates/systems/intel.template
   vision/systems/hardware/intel/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Intel the
   convention is `hardware.intel`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `hardware.intel.read`, `hardware.intel.write`, or
   `hardware.intel.admin.delete`.

3. **Map Intel's operations to step inputs.** Compute pressure derives from RDT counters; SGX enclave operations are first-class scope-bearing actions.

4. **Wire Intel's authentication into IAIso's identity bridge.**
   If Intel fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Intel integration and confirm pressure stays
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

- `vision/systems/hardware/intel/README.md`
- `vision/templates/systems/intel.template`
- `vision/systems/INDEX.md`

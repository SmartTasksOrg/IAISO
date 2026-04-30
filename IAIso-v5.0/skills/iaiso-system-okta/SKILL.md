---
name: iaiso-system-okta
description: "Use this skill when building or reviewing an IAIso integration with Okta (category: identity). Triggers on `Okta`, `identity.okta`, or any agent action that reads from or writes to Okta. Do not use this skill for unrelated identity systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Okta integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Okta,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Okta system template** as the starting point:

   ```
   vision/templates/systems/okta.template
   vision/systems/identity/okta/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Okta the
   convention is `identity.okta`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `identity.okta.read`, `identity.okta.write`, or
   `identity.okta.admin.delete`.

3. **Map Okta's operations to step inputs.** Read user/group membership → `tool_calls`; provisioning → writes; factor reset → high-stakes, broader scope.

4. **Wire Okta's authentication into IAIso's identity bridge.**
   If Okta fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Okta integration and confirm pressure stays
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

- `vision/systems/identity/okta/README.md`
- `vision/templates/systems/okta.template`
- `vision/systems/INDEX.md`

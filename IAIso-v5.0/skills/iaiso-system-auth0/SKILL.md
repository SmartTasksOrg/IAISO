---
name: iaiso-system-auth0
description: "Use this skill when building or reviewing an IAIso integration with Auth0 (category: identity). Triggers on `Auth0`, `identity.auth0`, or any agent action that reads from or writes to Auth0. Do not use this skill for unrelated identity systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Auth0 integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Auth0,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Auth0 system template** as the starting point:

   ```
   vision/templates/systems/auth0.template
   vision/systems/identity/auth0/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Auth0 the
   convention is `identity.auth0`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `identity.auth0.read`, `identity.auth0.write`, or
   `identity.auth0.admin.delete`.

3. **Map Auth0's operations to step inputs.** Reading Rules / Actions is read scope; deploying them is `identity.auth0.write`.

4. **Wire Auth0's authentication into IAIso's identity bridge.**
   If Auth0 fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Auth0 integration and confirm pressure stays
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

- `vision/systems/identity/auth0/README.md`
- `vision/templates/systems/auth0.template`
- `vision/systems/INDEX.md`

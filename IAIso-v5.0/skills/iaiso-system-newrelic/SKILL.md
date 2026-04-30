---
name: iaiso-system-newrelic
description: "Use this skill when building or reviewing an IAIso integration with New Relic (category: monitoring). Triggers on `New Relic`, `monitoring.newrelic`, or any agent action that reads from or writes to New Relic. Do not use this skill for unrelated monitoring systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# New Relic integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to New Relic,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the New Relic system template** as the starting point:

   ```
   vision/templates/systems/newrelic.template
   vision/systems/monitoring/newrelic/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For New Relic the
   convention is `monitoring.newrelic`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `monitoring.newrelic.read`, `monitoring.newrelic.write`, or
   `monitoring.newrelic.admin.delete`.

3. **Map New Relic's operations to step inputs.** NRQL queries → `tool_calls`. Custom event submissions → writes, broader scope.

4. **Wire New Relic's authentication into IAIso's identity bridge.**
   If New Relic fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the New Relic integration and confirm pressure stays
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

- `vision/systems/monitoring/newrelic/README.md`
- `vision/templates/systems/newrelic.template`
- `vision/systems/INDEX.md`

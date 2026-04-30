---
name: iaiso-system-datadog
description: "Use this skill when building or reviewing an IAIso integration with Datadog (category: monitoring). Triggers on `Datadog`, `monitoring.datadog`, or any agent action that reads from or writes to Datadog. Do not use this skill for unrelated monitoring systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Datadog integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Datadog,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Datadog system template** as the starting point:

   ```
   vision/templates/systems/datadog.template
   vision/systems/monitoring/datadog/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Datadog the
   convention is `monitoring.datadog`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `monitoring.datadog.read`, `monitoring.datadog.write`, or
   `monitoring.datadog.admin.delete`.

3. **Map Datadog's operations to step inputs.** Map agent decisions that read metrics to `tool_calls`; query depth (metric → dashboard → alert) maps to `depth`.

4. **Wire Datadog's authentication into IAIso's identity bridge.**
   If Datadog fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Datadog integration and confirm pressure stays
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

- `vision/systems/monitoring/datadog/README.md`
- `vision/templates/systems/datadog.template`
- `vision/systems/INDEX.md`

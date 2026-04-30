---
name: iaiso-system-prometheus
description: "Use this skill when building or reviewing an IAIso integration with Prometheus (category: monitoring). Triggers on `Prometheus`, `monitoring.prometheus`, or any agent action that reads from or writes to Prometheus. Do not use this skill for unrelated monitoring systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Prometheus integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Prometheus,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Prometheus system template** as the starting point:

   ```
   vision/templates/systems/prometheus.template
   vision/systems/monitoring/prometheus/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Prometheus the
   convention is `monitoring.prometheus`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `monitoring.prometheus.read`, `monitoring.prometheus.write`, or
   `monitoring.prometheus.admin.delete`.

3. **Map Prometheus's operations to step inputs.** PromQL queries map to `tool_calls`; alert-rule modifications map to writes and require broader scope.

4. **Wire Prometheus's authentication into IAIso's identity bridge.**
   If Prometheus fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Prometheus integration and confirm pressure stays
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

- `vision/systems/monitoring/prometheus/README.md`
- `vision/templates/systems/prometheus.template`
- `vision/systems/INDEX.md`

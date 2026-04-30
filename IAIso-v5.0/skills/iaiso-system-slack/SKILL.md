---
name: iaiso-system-slack
description: "Use this skill when building or reviewing an IAIso integration with Slack (category: collaboration). Triggers on `Slack`, `collab.slack`, or any agent action that reads from or writes to Slack. Do not use this skill for unrelated collaboration systems — pick the matching system skill."
version: 1.0.0
tier: P2
category: system
framework: IAIso v5.0
license: See ../LICENSE
---

# Slack integration for IAIso

## When this applies

An IAIso-governed agent needs to read from or write to Slack,
and you need that boundary to be pressure-accounted, scope-checked,
and audit-logged.

## Steps To Complete

1. **Use the Slack system template** as the starting point:

   ```
   vision/templates/systems/slack.template
   vision/systems/collaboration/slack/README.md
   ```

   Copy the template into your agent's prompt path. The standard
   six-step body (pressure check → delta calculation → scope
   verify → halt-or-execute → magnification → audit log) does the
   work; do not paraphrase it.

2. **Pick the consent scope namespace.** For Slack the
   convention is `collab.slack`. Sub-scopes follow the
   `<namespace>.<resource>.<action>` pattern, e.g.
   `collab.slack.read`, `collab.slack.write`, or
   `collab.slack.admin.delete`.

3. **Map Slack's operations to step inputs.** Reading messages → `tool_calls`; posting messages → writes with scope `collab.slack.post`; admin actions → broader scope.

4. **Wire Slack's authentication into IAIso's identity bridge.**
   If Slack fronts an OIDC provider, see the matching
   `iaiso-deploy-oidc-*` skill. Otherwise issue scoped
   ConsentScope tokens out of band and bind them to the
   `execution_id`.

5. **Test with the conformance harness.** Run a benign workload
   through the Slack integration and confirm pressure stays
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

- `vision/systems/collaboration/slack/README.md`
- `vision/templates/systems/slack.template`
- `vision/systems/INDEX.md`

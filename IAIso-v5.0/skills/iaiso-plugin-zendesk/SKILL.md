---
name: iaiso-plugin-zendesk
description: "Use this skill when wrapping Zendesk actions in IAIso pressure governance. Triggers on `Zendesk`, `@iaiso/zendesk`, or any AI-driven ticket response and routing flow that crosses an IAIso-governed agent. Do not use this skill for unrelated platforms or for general orchestrator integration."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# Zendesk plugin for IAIso

## When this applies

AI-driven ticket response and routing runs through Zendesk and an IAIso-governed agent
is in the loop somewhere — generating content, ranking, scoring,
or deciding.

## Steps To Complete

1. **Install the plugin** for Zendesk. The shipped plugin
   lives at `vision/plugins/zendesk/`.

2. **Wrap the agent-driven entry point** — not every Zendesk
   request, only the ones an agent reasons about. Wrapping too
   broadly produces noise and inflates pressure on benign user
   traffic.

3. **Map Zendesk actions to step inputs.** The signal that
   matters is: agent-issued ticket responses or escalation routing.

4. **Decide the failure mode.** When pressure escalates or
   releases, what should Zendesk return? Default in the
   reference plugin is HTTP 429 with `IAIso Safety` in the body;
   teams running customer-facing flows usually swap this for a
   graceful fallback. Document the choice in the plugin config.

5. **Confirm audit emission.** Every blocked or magnified action
   should produce an audit event with `kind` linking to the
   Zendesk request ID — this is the trail an investigator
   walks when something goes wrong in production.

## What this skill does NOT cover

- The IAIso pressure model — see
  `../iaiso-spec-pressure-model/SKILL.md`.
- Calibrating coefficients to your traffic — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `vision/plugins/zendesk/`
- `core/spec/pressure/README.md`

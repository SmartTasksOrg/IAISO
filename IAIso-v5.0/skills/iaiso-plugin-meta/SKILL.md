---
name: iaiso-plugin-meta
description: "Use this skill when wrapping Meta actions in IAIso pressure governance. Triggers on `Meta`, `@iaiso/meta`, or any Ads / Instagram / Facebook agent-driven campaigns flow that crosses an IAIso-governed agent. Do not use this skill for unrelated platforms or for general orchestrator integration."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# Meta plugin for IAIso

## When this applies

Ads / Instagram / Facebook agent-driven campaigns runs through Meta and an IAIso-governed agent
is in the loop somewhere — generating content, ranking, scoring,
or deciding.

## Steps To Complete

1. **Install the plugin** for Meta. The shipped plugin
   lives at `vision/plugins/meta/`.

2. **Wrap the agent-driven entry point** — not every Meta
   request, only the ones an agent reasons about. Wrapping too
   broadly produces noise and inflates pressure on benign user
   traffic.

3. **Map Meta actions to step inputs.** The signal that
   matters is: agent decisions that move spend or change targeting.

4. **Decide the failure mode.** When pressure escalates or
   releases, what should Meta return? Default in the
   reference plugin is HTTP 429 with `IAIso Safety` in the body;
   teams running customer-facing flows usually swap this for a
   graceful fallback. Document the choice in the plugin config.

5. **Confirm audit emission.** Every blocked or magnified action
   should produce an audit event with `kind` linking to the
   Meta request ID — this is the trail an investigator
   walks when something goes wrong in production.

## What this skill does NOT cover

- The IAIso pressure model — see
  `../iaiso-spec-pressure-model/SKILL.md`.
- Calibrating coefficients to your traffic — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `vision/plugins/meta/`
- `core/spec/pressure/README.md`

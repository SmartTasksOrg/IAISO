---
name: iaiso-plugin-magento
description: "Use this skill when wrapping Magento actions in IAIso pressure governance. Triggers on `Magento`, `@iaiso/magento`, or any AI-driven catalogue and merchandising flow that crosses an IAIso-governed agent. Do not use this skill for unrelated platforms or for general orchestrator integration."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# Magento plugin for IAIso

## When this applies

AI-driven catalogue and merchandising runs through Magento and an IAIso-governed agent
is in the loop somewhere — generating content, ranking, scoring,
or deciding.

## Steps To Complete

1. **Install the plugin** for Magento. The shipped plugin
   lives at `vision/plugins/magento/`.

2. **Wrap the agent-driven entry point** — not every Magento
   request, only the ones an agent reasons about. Wrapping too
   broadly produces noise and inflates pressure on benign user
   traffic.

3. **Map Magento actions to step inputs.** The signal that
   matters is: agent-driven price / catalogue changes.

4. **Decide the failure mode.** When pressure escalates or
   releases, what should Magento return? Default in the
   reference plugin is HTTP 429 with `IAIso Safety` in the body;
   teams running customer-facing flows usually swap this for a
   graceful fallback. Document the choice in the plugin config.

5. **Confirm audit emission.** Every blocked or magnified action
   should produce an audit event with `kind` linking to the
   Magento request ID — this is the trail an investigator
   walks when something goes wrong in production.

## What this skill does NOT cover

- The IAIso pressure model — see
  `../iaiso-spec-pressure-model/SKILL.md`.
- Calibrating coefficients to your traffic — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `vision/plugins/magento/`
- `core/spec/pressure/README.md`

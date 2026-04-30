---
name: iaiso-plugin-shopify
description: "Use this skill when wrapping Shopify actions in IAIso pressure governance. Triggers on `Shopify`, `@iaiso/shopify`, or any AI-driven merchandising and recommendations flow that crosses an IAIso-governed agent. Do not use this skill for unrelated platforms or for general orchestrator integration."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# Shopify plugin for IAIso

## When this applies

AI-driven merchandising and recommendations runs through Shopify and an IAIso-governed agent
is in the loop somewhere — generating content, ranking, scoring,
or deciding.

## Steps To Complete

1. **Install the plugin** for Shopify. The shipped plugin
   lives at `vision/plugins/shopify/`.

2. **Wrap the agent-driven entry point** — not every Shopify
   request, only the ones an agent reasons about. Wrapping too
   broadly produces noise and inflates pressure on benign user
   traffic.

3. **Map Shopify actions to step inputs.** The signal that
   matters is: agent-driven product surfacing or pricing.

4. **Decide the failure mode.** When pressure escalates or
   releases, what should Shopify return? Default in the
   reference plugin is HTTP 429 with `IAIso Safety` in the body;
   teams running customer-facing flows usually swap this for a
   graceful fallback. Document the choice in the plugin config.

5. **Confirm audit emission.** Every blocked or magnified action
   should produce an audit event with `kind` linking to the
   Shopify request ID — this is the trail an investigator
   walks when something goes wrong in production.

## What this skill does NOT cover

- The IAIso pressure model — see
  `../iaiso-spec-pressure-model/SKILL.md`.
- Calibrating coefficients to your traffic — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `vision/plugins/shopify/`
- `core/spec/pressure/README.md`

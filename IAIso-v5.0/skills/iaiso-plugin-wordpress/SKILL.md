---
name: iaiso-plugin-wordpress
description: "Use this skill when wrapping WordPress actions in IAIso pressure governance. Triggers on `WordPress`, `@iaiso/wordpress`, or any AI-driven content generation flow that crosses an IAIso-governed agent. Do not use this skill for unrelated platforms or for general orchestrator integration."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# WordPress plugin for IAIso

## When this applies

AI-driven content generation runs through WordPress and an IAIso-governed agent
is in the loop somewhere — generating content, ranking, scoring,
or deciding.

## Steps To Complete

1. **Install the plugin** for WordPress. The shipped plugin
   lives at `vision/plugins/wordpress/`.

2. **Wrap the agent-driven entry point** — not every WordPress
   request, only the ones an agent reasons about. Wrapping too
   broadly produces noise and inflates pressure on benign user
   traffic.

3. **Map WordPress actions to step inputs.** The signal that
   matters is: agent-authored posts or moderation decisions.

4. **Decide the failure mode.** When pressure escalates or
   releases, what should WordPress return? Default in the
   reference plugin is HTTP 429 with `IAIso Safety` in the body;
   teams running customer-facing flows usually swap this for a
   graceful fallback. Document the choice in the plugin config.

5. **Confirm audit emission.** Every blocked or magnified action
   should produce an audit event with `kind` linking to the
   WordPress request ID — this is the trail an investigator
   walks when something goes wrong in production.

## What this skill does NOT cover

- The IAIso pressure model — see
  `../iaiso-spec-pressure-model/SKILL.md`.
- Calibrating coefficients to your traffic — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `vision/plugins/wordpress/`
- `core/spec/pressure/README.md`

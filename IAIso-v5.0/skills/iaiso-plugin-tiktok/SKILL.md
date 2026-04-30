---
name: iaiso-plugin-tiktok
description: "Use this skill when wrapping TikTok actions in IAIso pressure governance. Triggers on `TikTok`, `@iaiso/tiktok`, or any AI-driven content / ads flow that crosses an IAIso-governed agent. Do not use this skill for unrelated platforms or for general orchestrator integration."
version: 1.0.0
tier: P2
category: plugin
framework: IAIso v5.0
license: See ../LICENSE
---

# TikTok plugin for IAIso

## When this applies

AI-driven content / ads runs through TikTok and an IAIso-governed agent
is in the loop somewhere — generating content, ranking, scoring,
or deciding.

## Steps To Complete

1. **Install the plugin** for TikTok. The shipped plugin
   lives at `vision/plugins/tiktok/`.

2. **Wrap the agent-driven entry point** — not every TikTok
   request, only the ones an agent reasons about. Wrapping too
   broadly produces noise and inflates pressure on benign user
   traffic.

3. **Map TikTok actions to step inputs.** The signal that
   matters is: agent-driven content publishing or ad spend.

4. **Decide the failure mode.** When pressure escalates or
   releases, what should TikTok return? Default in the
   reference plugin is HTTP 429 with `IAIso Safety` in the body;
   teams running customer-facing flows usually swap this for a
   graceful fallback. Document the choice in the plugin config.

5. **Confirm audit emission.** Every blocked or magnified action
   should produce an audit event with `kind` linking to the
   TikTok request ID — this is the trail an investigator
   walks when something goes wrong in production.

## What this skill does NOT cover

- The IAIso pressure model — see
  `../iaiso-spec-pressure-model/SKILL.md`.
- Calibrating coefficients to your traffic — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `vision/plugins/tiktok/`
- `core/spec/pressure/README.md`

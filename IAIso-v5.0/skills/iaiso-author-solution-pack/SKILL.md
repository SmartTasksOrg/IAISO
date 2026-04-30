---
name: iaiso-author-solution-pack
description: "Use this skill to author a new solution-pack template under `vision/templates/sol/`. Triggers on industry/use-case templates, prompt-contract authoring. Do not use it to edit agent system prompts directly — see `iaiso-author-agent-system-prompt`."
version: 1.0.0
tier: P3
category: authoring
framework: IAIso v5.0
license: See ../LICENSE
---

# Authoring an IAIso solution-pack

## When this applies

A new industry × use-case combination needs a reproducible
starting prompt and policy. Existing packs live at
`vision/templates/sol/sol.<industry>.<usecase>-v1.template`.

## Steps To Complete

1. **Pick the industry × use-case slug.** Lowercase, dotted,
   versioned: `sol.healthcare.diagnostics-v1`. Versioning
   lets you migrate without breaking deployments pinned to v1.

2. **Open with the canonical role / invariant block.**
   Verbatim — see `iaiso-author-agent-system-prompt`. Solution
   packs do not paraphrase the invariants.

3. **Add the consent-enforcement block** from
   `vision/templates/consent-enforcement.template`.

4. **State the sector workflow concretely.** Allowed tools,
   prohibited actions, escalation triggers specific to the
   sector. The pack is opinionated; vague packs are useless.

5. **Ship a matching policy snippet.** Every pack should
   carry a `policy.example.yaml` with calibrated coefficients
   and thresholds tuned to the workflow.

6. **Test against the conformance harness** with a sample
   trajectory. The pack passes if benign workflows stay below
   escalation and adversarial probes cross cleanly.

## What this skill does NOT cover

- Picking pressure coefficients — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `vision/templates/sol/`
- existing packs as worked examples

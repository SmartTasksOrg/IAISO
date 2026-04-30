---
name: iaiso-integ-haystack
description: "Use this skill when wrapping a Haystack agent or pipeline with IAIso pressure governance. Triggers on `Haystack`, `IAIsoPipelineWrapper`, or `iaiso.integrations.haystack`. Do not use for raw LLM-provider clients (see iaiso-llm-* skills) or for non-Haystack orchestrators."
version: 1.0.0
tier: P2
category: integration
framework: IAIso v5.0
license: See ../LICENSE
---

# Haystack integration for IAIso

## When this applies

Your team is running agents on Haystack and you need every step
inside the orchestrator to flow through IAIso's pressure engine,
consent verification, and audit emission. This skill tells you
exactly which call boundary to wrap and what records to attach.

## Steps To Complete

1. **Install the integration package.** The reference SDK ships
   this wrapper as part of `core/iaiso-python` (or its language
   port).

   ```python
   from iaiso.integrations.haystack import IAIsoPipelineWrapper
   ```

2. **Wrap at the orchestrator's outermost call boundary** — the
   one place every step of every agent passes through. For
   Haystack that is documented in
   `vision/integrations/integ-haystack/README.md`.

   ```python
   safe = IAIsoPipelineWrapper(
       your_orchestrator,
       pressure_threshold=0.85,
       enable_magnification=True,
   )
   ```

3. **Attach a consent scope** before invoking, per
   `iaiso-runtime-consent-scope-check`. Do not run a Haystack
   pipeline with no scope attached — the engine will emit
   `consent.missing` on every tool call.

4. **Hook the framework's callbacks** so step accounting matches
   what the underlying LLM provider reports. Mismatches are the
   single most common calibration bug — see
   `iaiso-deploy-calibration` for the methodology.

5. **Forward the framework's run-id (or equivalent) into IAIso's
   `execution_id`.** This is what makes audit traces correlate
   across systems.

## Framework-specific gotcha

Pipeline.run is the boundary. For Agent components inside a pipeline, the agent step counts as one IAIso step regardless of internal hops.



## What this skill does NOT cover

- The IAIso runtime contract that any agent (regardless of
  framework) must observe — see
  `../iaiso-runtime-governed-agent/SKILL.md`.
- Calibrating pressure coefficients to match Haystack's
  step granularity — see `../iaiso-deploy-calibration/SKILL.md`.
- Picking an LLM-provider middleware to sit underneath
  Haystack — see the `iaiso-llm-*` family.

## References

- `vision/integrations/integ-haystack/README.md`
- `core/spec/pressure/README.md` — what the wrapper enforces
- `core/spec/events/README.md` — events the wrapper emits

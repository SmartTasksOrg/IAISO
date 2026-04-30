---
name: iaiso-integ-microsoft-copilot
description: "Use this skill when wrapping a Microsoft Copilot Studio agent or pipeline with IAIso pressure governance. Triggers on `Microsoft Copilot Studio`, `IAIsoCopilotConnector`, or `iaiso.integrations.copilot`. Do not use for raw LLM-provider clients (see iaiso-llm-* skills) or for non-Microsoft Copilot Studio orchestrators."
version: 1.0.0
tier: P2
category: integration
framework: IAIso v5.0
license: See ../LICENSE
---

# Microsoft Copilot Studio integration for IAIso

## When this applies

Your team is running agents on Microsoft Copilot Studio and you need every step
inside the orchestrator to flow through IAIso's pressure engine,
consent verification, and audit emission. This skill tells you
exactly which call boundary to wrap and what records to attach.

## Steps To Complete

1. **Install the integration package.** The reference SDK ships
   this wrapper as part of `core/iaiso-python` (or its language
   port).

   ```python
   from iaiso.integrations.copilot import IAIsoCopilotConnector
   ```

2. **Wrap at the orchestrator's outermost call boundary** — the
   one place every step of every agent passes through. For
   Microsoft Copilot Studio that is documented in
   `vision/integrations/integ-microsoft-copilot/README.md`.

   ```python
   safe = IAIsoCopilotConnector(
       your_orchestrator,
       pressure_threshold=0.85,
       enable_magnification=True,
   )
   ```

3. **Attach a consent scope** before invoking, per
   `iaiso-runtime-consent-scope-check`. Do not run a Microsoft Copilot Studio
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

Wrap at the topic boundary. Per-message wrapping loses the topic-level task scope and produces over-frequent escalations.



## What this skill does NOT cover

- The IAIso runtime contract that any agent (regardless of
  framework) must observe — see
  `../iaiso-runtime-governed-agent/SKILL.md`.
- Calibrating pressure coefficients to match Microsoft Copilot Studio's
  step granularity — see `../iaiso-deploy-calibration/SKILL.md`.
- Picking an LLM-provider middleware to sit underneath
  Microsoft Copilot Studio — see the `iaiso-llm-*` family.

## References

- `vision/integrations/integ-microsoft-copilot/README.md`
- `core/spec/pressure/README.md` — what the wrapper enforces
- `core/spec/events/README.md` — events the wrapper emits

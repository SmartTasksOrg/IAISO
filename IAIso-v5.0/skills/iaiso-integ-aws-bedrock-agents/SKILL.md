---
name: iaiso-integ-aws-bedrock-agents
description: "Use this skill when wrapping a AWS Bedrock Agents agent or pipeline with IAIso pressure governance. Triggers on `AWS Bedrock Agents`, `IAIsoBedrockAgentClient`, or `iaiso.integrations.agents`. Do not use for raw LLM-provider clients (see iaiso-llm-* skills) or for non-AWS Bedrock Agents orchestrators."
version: 1.0.0
tier: P2
category: integration
framework: IAIso v5.0
license: See ../LICENSE
---

# AWS Bedrock Agents integration for IAIso

## When this applies

Your team is running agents on AWS Bedrock Agents and you need every step
inside the orchestrator to flow through IAIso's pressure engine,
consent verification, and audit emission. This skill tells you
exactly which call boundary to wrap and what records to attach.

## Steps To Complete

1. **Install the integration package.** The reference SDK ships
   this wrapper as part of `core/iaiso-python` (or its language
   port).

   ```python
   from iaiso.integrations.bedrock_agents import IAIsoBedrockAgentClient
   ```

2. **Wrap at the orchestrator's outermost call boundary** — the
   one place every step of every agent passes through. For
   AWS Bedrock Agents that is documented in
   `vision/integrations/integ-aws-bedrock-agents/README.md`.

   ```python
   safe = IAIsoBedrockAgentClient(
       your_orchestrator,
       pressure_threshold=0.85,
       enable_magnification=True,
   )
   ```

3. **Attach a consent scope** before invoking, per
   `iaiso-runtime-consent-scope-check`. Do not run a AWS Bedrock Agents
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

Wrap the InvokeAgent boundary. Trace events from Bedrock map cleanly onto IAIso step inputs (input/output tokens come back in the trace).



## What this skill does NOT cover

- The IAIso runtime contract that any agent (regardless of
  framework) must observe — see
  `../iaiso-runtime-governed-agent/SKILL.md`.
- Calibrating pressure coefficients to match AWS Bedrock Agents's
  step granularity — see `../iaiso-deploy-calibration/SKILL.md`.
- Picking an LLM-provider middleware to sit underneath
  AWS Bedrock Agents — see the `iaiso-llm-*` family.

## References

- `vision/integrations/integ-aws-bedrock-agents/README.md`
- `core/spec/pressure/README.md` — what the wrapper enforces
- `core/spec/events/README.md` — events the wrapper emits

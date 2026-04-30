---
name: iaiso-llm-bedrock
description: "Use this skill when integrating the AWS Bedrock LLM into an IAIso bounded execution. Triggers on `BoundedBedrock`, `BoundedBedrock`, or any direct call to AWS Bedrock's SDK from IAIso-governed code. Do not use this skill for orchestrator wrappers that already sit above the provider — use the matching `iaiso-integ-*` skill instead."
version: 1.0.0
tier: P2
category: llm-provider
framework: IAIso v5.0
license: See ../LICENSE
---

# AWS Bedrock middleware for IAIso

## When this applies

The agent calls AWS Bedrock directly (no orchestrator in between)
and every call must be accounted for in the pressure engine and
emitted as audit events.

## Steps To Complete

1. **Pick the bounded client.**

   ```python
   from iaiso.middleware.bedrock import BoundedBedrock
   ```

   ```typescript
   import { BoundedBedrock } from "@iaiso/core";
   ```

2. **Hand it the same execution context** the rest of your code
   uses. The wrapper is a `AWS Bedrock` SDK shim — every
   provider-side call records a step on the bound engine.

3. **Map provider response usage onto step inputs.** For
   AWS Bedrock the canonical mapping is:

   - `tokens` ← total of prompt + completion as reported by
     AWS Bedrock's usage object.
   - `tool_calls` ← number of tool/function-call entries in the
     response (1 per call, not 1 per round-trip retry).
   - `depth` ← only set this if you are running multi-step
     planning chains — leave at 0 for single-shot calls.

4. **Honour the provider's call boundary.** Bedrock surfaces different usage fields per model family. The middleware normalises to (input_tokens, output_tokens); trust that rather than picking model-specific fields yourself.

5. **Trust the wrapper's escalation behaviour.** When pressure
   reaches `escalation_threshold`, the wrapper raises
   `EscalationRaised` (or the language equivalent) before the
   provider call goes out — do not catch this and retry blindly.
   Hand control to `iaiso-runtime-handle-escalation`.

## What this skill does NOT cover

- Pricing / token-budget logic — the engine cares about safety
  pressure, not money. Token budgets live in your provider
  account.
- The runtime conduct of the agent calling the provider — see
  `../iaiso-runtime-governed-agent/SKILL.md`.

## References

- `core/iaiso-python/iaiso/middleware/bedrock.py`
- `core/iaiso-node/src/middleware/bedrock.ts`
- `core/spec/pressure/README.md` — step semantics

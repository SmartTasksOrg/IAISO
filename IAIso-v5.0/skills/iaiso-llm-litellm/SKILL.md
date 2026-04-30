---
name: iaiso-llm-litellm
description: "Use this skill when integrating the LiteLLM proxy LLM into an IAIso bounded execution. Triggers on `BoundedLiteLLM`, `BoundedLiteLLM`, or any direct call to LiteLLM proxy's SDK from IAIso-governed code. Do not use this skill for orchestrator wrappers that already sit above the provider — use the matching `iaiso-integ-*` skill instead."
version: 1.0.0
tier: P2
category: llm-provider
framework: IAIso v5.0
license: See ../LICENSE
---

# LiteLLM proxy middleware for IAIso

## When this applies

The agent calls LiteLLM proxy directly (no orchestrator in between)
and every call must be accounted for in the pressure engine and
emitted as audit events.

## Steps To Complete

1. **Pick the bounded client.**

   ```python
   from iaiso.middleware.litellm import BoundedLiteLLM
   ```

   ```typescript
   import { BoundedLiteLLM } from "@iaiso/core";
   ```

2. **Hand it the same execution context** the rest of your code
   uses. The wrapper is a `LiteLLM proxy` SDK shim — every
   provider-side call records a step on the bound engine.

3. **Map provider response usage onto step inputs.** For
   LiteLLM proxy the canonical mapping is:

   - `tokens` ← total of prompt + completion as reported by
     LiteLLM proxy's usage object.
   - `tool_calls` ← number of tool/function-call entries in the
     response (1 per call, not 1 per round-trip retry).
   - `depth` ← only set this if you are running multi-step
     planning chains — leave at 0 for single-shot calls.

4. **Honour the provider's call boundary.** LiteLLM normalises across providers; account at the litellm.completion boundary, not the underlying provider. The wrapper handles provider-specific token reporting through LiteLLM's normalised usage.

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

- `core/iaiso-python/iaiso/middleware/litellm.py`
- `core/iaiso-node/src/middleware/litellm.ts`
- `core/spec/pressure/README.md` — step semantics

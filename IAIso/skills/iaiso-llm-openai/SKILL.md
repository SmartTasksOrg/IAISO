---
name: iaiso-llm-openai
description: "Use this skill when integrating the OpenAI LLM into an IAIso bounded execution. Triggers on `BoundedOpenAI`, `BoundedOpenAI`, or any direct call to OpenAI's SDK from IAIso-governed code. Do not use this skill for orchestrator wrappers that already sit above the provider — use the matching `iaiso-integ-*` skill instead."
version: 1.0.0
tier: P2
category: llm-provider
framework: IAIso v5.0
license: See ../LICENSE
---

# OpenAI middleware for IAIso

## When this applies

The agent calls OpenAI directly (no orchestrator in between)
and every call must be accounted for in the pressure engine and
emitted as audit events.

## Steps To Complete

1. **Pick the bounded client.**

   ```python
   from iaiso.middleware.openai import BoundedOpenAI
   ```

   ```typescript
   import { BoundedOpenAI } from "@iaiso/core";
   ```

2. **Hand it the same execution context** the rest of your code
   uses. The wrapper is a `OpenAI` SDK shim — every
   provider-side call records a step on the bound engine.

3. **Map provider response usage onto step inputs.** For
   OpenAI the canonical mapping is:

   - `tokens` ← total of prompt + completion as reported by
     OpenAI's usage object.
   - `tool_calls` ← number of tool/function-call entries in the
     response (1 per call, not 1 per round-trip retry).
   - `depth` ← only set this if you are running multi-step
     planning chains — leave at 0 for single-shot calls.

4. **Honour the provider's call boundary.** Function-calling responses contain tool_calls in the message; map them 1:1 onto IAIso `tool_calls`. Retries due to 429s are NOT extra steps — skip them in accounting.

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

- `core/iaiso-python/iaiso/middleware/openai.py`
- `core/iaiso-node/src/middleware/openai.ts`
- `core/spec/pressure/README.md` — step semantics

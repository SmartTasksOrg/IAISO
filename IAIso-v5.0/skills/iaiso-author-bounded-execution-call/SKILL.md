---
name: iaiso-author-bounded-execution-call
description: "Use this skill when wrapping new code in `BoundedExecution.run(...)` or its language equivalent. Do not use it for already-wrapped code that just needs a config tweak — load `iaiso-deploy-policy-authoring` instead."
version: 1.0.0
tier: P0
category: authoring
framework: IAIso v5.0
license: See ../LICENSE
---

# Wrapping code in a BoundedExecution

## When this applies

A code path that calls an LLM, hits a tool, or otherwise
qualifies as agentic is being placed under IAIso. This skill
is the canonical wrap pattern across all nine SDKs.

## Steps To Complete

1. **Pick the canonical wrapper for your language.** The
   reference SDKs all expose the same shape:

   ```python
   # Python
   from iaiso import BoundedExecution, PressureConfig
   with BoundedExecution.start(config=PressureConfig()) as exec:
       outcome = exec.record_tool_call(name="search", tokens=500)
   ```

   ```typescript
   // Node / TypeScript
   import { BoundedExecution, PressureConfig } from "@iaiso/core";
   await BoundedExecution.run({ config: new PressureConfig() }, async (exec) => {
     const outcome = exec.recordToolCall({ name: "search", tokens: 500 });
   });
   ```

   ```go
   // Go
   core.Run(core.BoundedExecutionOptions{AuditSink: sink}, func(exec *core.BoundedExecution) error {
       outcome, _ := exec.RecordToolCall("search", 500)
       return nil
   })
   ```

   Equivalents for Rust / Java / C# / PHP / Ruby / Swift are
   in their respective SDK READMEs.

2. **Attach a consent scope at start.** If the execution does
   any privileged action, attach a token; otherwise the first
   privileged call emits `consent.missing` and halts.

3. **Pick a stable `system_id` / `execution_id`.**
   `execution_id` is what cross-correlates events. Use a UUID
   per logical execution — not per process, not per request.

4. **Set the audit sink.** For dev work, `MemorySink` is
   enough. For prod, see `iaiso-audit-sink-selection`.

5. **Do NOT swallow `ExecutionLocked`.** The locked state is
   a contract; retrying through it defeats the framework.
   Surface the lock to the orchestrator and let
   `iaiso-runtime-handle-escalation` take over.

6. **Close the execution cleanly.** All language ports
   support context-manager / try-with-resources / `defer`
   semantics. Use them so `execution.closed` lands in audit.

## Common mistakes

- Creating one BoundedExecution per HTTP request when the
  agent's logical task spans many requests. The execution
  should match the *task*, not the transport.
- Sharing a BoundedExecution across goroutines / threads
  without thinking. The reference engines are not goroutine-
  safe by default; coordinate via the Redis coordinator if
  you need multi-process or multi-thread sharing.
- Forgetting `audit_sink=` and silently emitting nothing.

## What this skill does NOT cover

- Provider-specific wrapping — see `iaiso-llm-*`.
- Orchestrator-specific wrapping — see `iaiso-integ-*`.

## References

- `core/iaiso-python/iaiso/core/execution.py`
- `core/iaiso-node/src/core/execution.ts`
- top-level `README.md` quick-start blocks

---
name: iaiso-author-bounded-execution-call
description: "Use this skill when wrapping new code in a BoundedExecution. Do not use it for already-wrapped code that just needs a config tweak — load `iaiso-deploy-policy-authoring` instead."
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

1. **Pick the canonical wrapper for your language.** The shapes are close but
   not identical. Python has no `run()`; it is a context manager. Node and Go
   expose `run` / `Run`.

   ```python
   # Python — context manager, no run()
   from iaiso import BoundedExecution, PressureConfig
   from iaiso.audit import JsonlFileSink

   config = PressureConfig(token_coefficient=0.011)  # calibrate; see step 4
   with BoundedExecution.start(
       config=config,
       audit_sink=JsonlFileSink("audit.jsonl"),
       enforcement_mode="strict",
       calibration_artifact="calibration/2026-07-01.json",
   ) as execution:
       outcome = execution.record_tool_call(name="search", tokens=500)
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

4. **Set the audit sink, and set `enforcement_mode`.** For dev work,
   `MemorySink` is enough. For prod, see `iaiso-audit-sink-selection`.

   Under `enforcement_mode="strict"` an omitted sink is a construction error,
   not a default — because an execution nobody can observe is not governed. The
   same guard refuses library-default coefficients with no calibration artifact.
   See `iaiso-deploy-enforcement-mode`. Available in Python, Node, and Go only.

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
- Forgetting `audit_sink=` and silently emitting nothing. Under `strict` this
  is refused at boot; under `permissive` it warns once and proceeds.
- Passing `PressureConfig()` with library defaults into production. The defaults
  are placeholders; thresholds will never fire or always fire.
- Assuming the wrapper contains the agent. It bounds a cooperating loop. See
  `iaiso-mental-model`.

## What this skill does NOT cover

- Provider-specific wrapping — see `iaiso-llm-*`.
- Orchestrator-specific wrapping — see `iaiso-integ-*`.
- Boot-time refusal — see `iaiso-deploy-enforcement-mode`.
- Spend caps — see `iaiso-runtime-cost-governance`.

## References

- `core/iaiso-python/iaiso/core/execution.py`
- `core/iaiso-node/src/core/execution.ts`
- top-level `README.md` quick-start blocks

---
name: iaiso-runtime-cost-governance
description: "Use this skill when an execution needs a dollar budget, when spend must be attributed per model or per tag, or when someone asks why an engine locked with reason budget_exceeded. Do not use it for pressure thresholds, which are the actual control loop — load `iaiso-deploy-threshold-tuning` instead."
version: 1.0.0
tier: P1
category: runtime
framework: IAIso v5.0
license: See ../LICENSE
---

# Bounding and attributing spend

## When this applies

An execution calls priced models and the operator needs a cap, an attribution
trail, or both. Introduced in spec 1.1; available in Python, Node, and Go.

## Steps To Complete

1. **Price the models you actually call.** `model_costs` is USD per 1M tokens.

   ```python
   from iaiso import BoundedExecution, PressureConfig
   from iaiso.audit import JsonlFileSink

   config = PressureConfig(
       token_coefficient=0.011,
       model_costs={"claude-sonnet-4-6": 3.0, "claude-haiku-4-5": 0.8},
       budget_usd=5.00,
   )
   ```

   An unpriced model is unmetered, not an error. That is deliberate: a missing
   price should not halt an execution, it should show up as zero spend and be
   noticed.

2. **Name the model on every accounting call**, or the tokens are free:

   ```python
   with BoundedExecution.start(config=config,
                               audit_sink=JsonlFileSink("audit.jsonl"),
                               enforcement_mode="strict",
                               calibration_artifact="calibration/2026-07-01.json") as ex:
       ex.record_tokens(response.usage.output_tokens,
                        model="claude-sonnet-4-6",
                        tag="synthesis")
       print(ex.spend_usd)
   ```

3. **Expect a lock, not a new state.** Exceeding `budget_usd` reuses the
   existing lock path and emits `engine.locked` with
   `reason: "budget_exceeded"`. No new lifecycle state exists, so the wire
   format is unchanged. The next accounting call raises `ExecutionLocked`.

4. **Read spend back out of the audit log**, grouped however you need:

   ```bash
   iaiso audit spend --group-by tag audit.jsonl
   iaiso audit spend --group-by execution_id audit.jsonl
   ```

5. **Know that `spend_usd` only appears when priced.** The `engine.step` event
   carries `spend_usd` only when `model_costs` is set, so consumers of the older
   event envelope never see a key they did not opt into.

## What cost governance is not

Cost is a **readout**. Pressure is the **control**. A budget cap stops an
execution after the money is spent; it does not prevent the spend. If you want
the loop to stop before it runs away, tune the pressure coefficients.

IAIso does not choose a cheaper model, compress prompts, or cache. It bounds and
attributes spend; it does not optimise it. Pair it with a routing or caching
layer.

## Common mistakes

- Setting `budget_usd` without `model_costs`. Spend stays zero and the cap never
  fires.
- Treating a budget lock as a rate limit. It is terminal until `reset()`.
- Forgetting `model=` on `record_tokens`, then wondering why `spend_usd` is 0.0.

## What this skill does NOT cover

- Boot-time refusal — see `iaiso-deploy-enforcement-mode`.
- Coefficient derivation — see `iaiso-deploy-calibration`.
- Audit sink choice — see `iaiso-audit-sink-selection`.

## References

- `core/iaiso-python/iaiso/core/engine.py`
- `core/spec/events/vectors.json`

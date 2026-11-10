---
name: iaiso-spec-pressure-model
description: "Use this skill when computing, validating, or debugging pressure values — anything involving `escalation_threshold`, `release_threshold`, the step equation, the four lifecycle states, or the 1e-9 floating-point tolerance. Do not use it for picking coefficients (see `iaiso-deploy-calibration`)."
version: 1.0.0
tier: P0
category: spec
framework: IAIso v5.0
license: See ../LICENSE
---

# IAIso pressure model — implementation contract

## When this applies

You are reading pressure values, computing them, or asserting
against them. This skill is the operational summary of
`core/spec/pressure/README.md` — the spec wins where they
disagree.

## Steps To Complete

1. **Apply the step equation exactly as specified.** Given
   previous pressure `p_{i-1}` and step input
   `(tokens_i, tool_calls_i, depth_i, tag_i)` with coefficients
   `C_tok`, `C_tool`, `C_depth`, `D_step`, `D_time`:

   ```
   elapsed_i = max(0, t_i − t_{i-1})
   delta_i   = (tokens_i / 1000) * C_tok
             + tool_calls_i      * C_tool
             + depth_i           * C_depth
   decay_i   = D_step + elapsed_i * D_time
   p_i       = clamp(p_{i-1} + delta_i − decay_i, 0, 1)
   ```

   `clamp(x, 0, 1) = max(0, min(x, 1))`. The three delta terms
   are non-negative and may be summed in any order — IEEE-754
   evaluation order is not normative.

2. **Check thresholds in the documented order — release first,
   escalation second.** Reversing this is the most common
   porting bug.

   ```
   if p_i ≥ release_threshold:
       emit engine.release; pressure ← 0
       if post_release_lock: lifecycle ← LOCKED; emit engine.locked
       else                : lifecycle ← RUNNING
       return RELEASED
   elif p_i ≥ escalation_threshold:
       lifecycle ← ESCALATED
       emit engine.escalation
       return ESCALATED
   else:
       lifecycle stays RUNNING; return OK
   ```

3. **Honour the LOCKED state.** When `step()` is called while
   `lifecycle == LOCKED`:

   - emit `engine.step.rejected` with `reason="locked"`;
   - DO NOT increment `step`;
   - DO NOT update `pressure`, `last_delta`, or `last_step_at`;
   - return `LOCKED`.

   Only `reset()` escapes. Resetting clears pressure, step,
   `last_delta`, sets lifecycle to `INIT`, and re-stamps
   `last_step_at` from the clock.

4. **Validate the configuration before constructing the
   engine.** Reject:

   - either threshold outside `[0, 1]`;
   - `release_threshold ≤ escalation_threshold`;
   - any non-negative field below zero.

5. **Compare implementations within `1e-9` absolute tolerance.**
   Bit-exact is allowed; looser is not. Integer/fixed-point
   implementations must document the scaling and stay within
   the tolerance.

## Edge cases that are NOT bugs

- `last_delta` records the **net** (`delta − decay`) but
  `engine.step` events emit **gross** `delta` and `decay`
  separately. Auditors who difference these get net.
- `RELEASED` is a transient lifecycle value — it appears in
  events but the engine never observably sits in `RELEASED`
  after a step returns.
- Threshold equality counts: `p == 0.85` with default
  escalation is an escalation, `p == 0.95` is a release.

## What this skill does NOT cover

- Picking coefficients — see
  `../iaiso-deploy-calibration/SKILL.md`.
- Picking thresholds — see
  `../iaiso-deploy-threshold-tuning/SKILL.md`.
- Audit event payloads — see
  `../iaiso-spec-audit-events/SKILL.md`.

## References

- `core/spec/pressure/README.md` (normative)
- `core/spec/pressure/vectors.json` (20 conformance vectors)

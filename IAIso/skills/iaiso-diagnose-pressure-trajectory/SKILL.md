---
name: iaiso-diagnose-pressure-trajectory
description: "Use this skill when investigating why pressure is rising (or escalating, or releasing) more than expected. Do not use it for diagnosing consent failures — see `iaiso-diagnose-consent-failure`."
version: 1.0.0
tier: P3
category: diagnostics
framework: IAIso v5.0
license: See ../LICENSE
---

# Diagnosing a pressure trajectory

## When this applies

The deployment is reporting pressure climbing too fast, or
too slow, or oscillating, or escalating on benign workloads.

## Steps To Complete

1. **Pull the full step sequence for a representative
   execution_id.** Plot pressure over step index. Three
   shapes diagnose three problems:

   - **Steady climb to release** → coefficients too high, or
     dissipation too low.
   - **Plateau just below escalation** → working as designed
     OR the agent is gaming the threshold (proxy
     optimization).
   - **Oscillation** → bursty workload, dissipation_per_step
     dominating, calibration mismatch.

2. **Inspect the per-step gross delta.** `engine.step.data.delta`
   (gross). Which contribution dominates — tokens, tool calls,
   depth? That's the coefficient to tune first.

3. **Inspect dissipation effectiveness.** Compute
   `delta − decay` per step. If decay barely moves the
   needle, your `dissipation_per_step` is too low.

4. **Cross-check coefficient calibration.** When was the
   last calibration run? On what workload? Workload drift
   is the most common cause of trajectory surprise.

5. **Differentiate calibration drift from adversarial
   behaviour.** Drift looks the same across many executions;
   gaming localises to specific prompts or users. Group by
   user / system_id / prompt template.

## What this skill does NOT cover

- Choosing new coefficients — see
  `../iaiso-deploy-calibration/SKILL.md`.

## References

- `core/spec/events/README.md` (`engine.step.data`)

---
name: iaiso-deploy-calibration
description: "Use this skill when picking real coefficients (`token_coefficient`, `tool_coefficient`, `depth_coefficient`, `dissipation_per_step`) for a specific workload. The defaults are starting points, not tuned values. Do not use it for picking thresholds — see `iaiso-deploy-threshold-tuning`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Calibrating IAIso pressure coefficients

## When this applies

A deployment is moving past defaults. The
`core/spec/pressure/README.md §2` table is explicit: the
default coefficients are reasonable on the reference scenarios
in `evals/`, not on your workload. Calibration is what makes
threshold behaviour defensible in audit.

## Steps To Complete

1. **Record real trajectories from your agents.** Use the
   shipped harnesses:

   ```
   core/iaiso-python/scripts/record_swebench.py
   core/iaiso-python/scripts/record_gaia.py
   ```

   For a custom workload, replace the agent loop in those
   scripts with your own. Each trajectory captures the
   sequence of `(tokens, tool_calls, depth, elapsed)` per
   step.

2. **Separate benign and adversarial trajectories.** The
   calibration goal is: benign workloads stay below
   `escalation_threshold` for the typical task length;
   adversarial workloads cross it. Without both, you cannot
   fit the curve.

3. **Fit coefficients to satisfy both goals.** The reference
   methodology in `core/docs/calibration.md` does a
   constrained optimisation:

   - minimise mean(p_max_per_benign_run) − target_benign;
   - subject to mean(p_max_per_adv_run) ≥ escalation_threshold;
   - regularise toward the spec defaults so the result stays
     readable.

   Do not eyeball — single-trajectory tuning over-fits and
   fails on day-2 traffic.

4. **Validate on a held-out trajectory set.** A calibration
   that scores 100% on training data and 60% on held-out has
   overfit. Aim for ≥95% benign-stay-below and
   ≥95% adversarial-cross.

5. **Document the calibration run.** Save the trajectory
   hashes, the optimisation seed, the resulting coefficients,
   and a one-paragraph rationale into `policy.metadata`. This
   is what an auditor will ask for first.

## Common mistakes

- Calibrating only on benign data. The thresholds become
  either always-trip (too tight) or never-trip (too loose).
- Reusing coefficients across workloads with very different
  tool-call density. The same `tool_coefficient` is wrong for
  a chat agent and a research agent.
- Skipping the regularisation. Coefficients miles from
  defaults are usually a sign that the workload is not what
  you think it is, not that the defaults are wrong.

## What this skill does NOT cover

- Picking the threshold values themselves — see
  `../iaiso-deploy-threshold-tuning/SKILL.md`.
- Per-step pressure math — see
  `../iaiso-spec-pressure-model/SKILL.md`.

## References

- `core/docs/calibration.md`
- `core/iaiso-python/scripts/record_swebench.py`
- `core/iaiso-python/scripts/record_gaia.py`

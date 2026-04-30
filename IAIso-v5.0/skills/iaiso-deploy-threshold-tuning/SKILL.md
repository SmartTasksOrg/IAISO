---
name: iaiso-deploy-threshold-tuning
description: "Use this skill when picking `escalation_threshold` and `release_threshold` for a deployment. Triggers on threshold value choices, organisational scale changes, or new regulatory regimes. Do not use it to fit coefficients — see `iaiso-deploy-calibration`."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Tuning IAIso thresholds

## When this applies

Defaults are 0.85 / 0.95. Your workload, organisation size,
or regulatory posture suggests something else. This skill is
the framework's recommendation surface plus the constraints
you cannot violate.

## Steps To Complete

1. **Honour the hard constraint.** `release_threshold > escalation_threshold`,
   both in `[0, 1]`. Loaders enforce this; setting them
   equal (or out of range) prevents the policy from loading.

2. **Match thresholds to organisational scale.** The
   `vision/systems/INDEX.md` recommendation table:

   | Scale       | Employees   | Escalation | Release  | Monitoring |
   |-------------|-------------|------------|----------|------------|
   | Small       | 1–50        | 0.80       | 0.92     | 5 minutes  |
   | Medium      | 51–500      | 0.85       | 0.95     | 1 minute   |
   | Large       | 501–5000    | 0.85       | 0.95     | 30 seconds |
   | Enterprise  | 5000+       | 0.90       | 0.97     | 10 seconds |

   Smaller orgs trip earlier (lower escalation, smaller
   buffer to release) because they have less observability
   headroom. Enterprises run a higher escalation threshold
   because they have continuous monitoring to catch drift.

3. **Adjust by sector.** Add the regulatory delta:

   - Healthcare / pharma: −0.05 from baseline (catch earlier).
   - Finance / payments: −0.05 from baseline.
   - Critical infrastructure (energy, water): −0.10 (Layer 6
     considerations apply — see
     `iaiso-layer-6-existential-safeguard`).
   - Internal tooling (no external impact): +0.05 ok.

4. **Validate against your benign p_max distribution.** Run
   the calibration trajectories and confirm the chosen
   escalation threshold sits at roughly the 90–95th percentile
   of benign max-pressure. Lower → false escalations; higher
   → adversarial workloads slip through.

5. **Simulate.** Use `vision/scripts/simulate_pressure.py`
   (or its successor in `core/`) with your coefficients and
   thresholds to draw the curve. If release fires before
   escalation visibly, your thresholds are inverted.

## What you NEVER do

- Set `release_threshold` to 1.0 to "never release". Pressure
  clamps to `[0, 1]`; the engine will release at 1.0 and you
  will discover that under load.
- Move thresholds without re-recording calibration data. Even
  a 0.05 shift can move benign p_max above escalation.

## What this skill does NOT cover

- Coefficient calibration — see
  `../iaiso-deploy-calibration/SKILL.md`.
- The math — see `../iaiso-spec-pressure-model/SKILL.md`.

## References

- `vision/systems/INDEX.md` — scale recommendations
- `vision/scripts/simulate_pressure.py`

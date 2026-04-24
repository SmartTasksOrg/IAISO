# Empirical Calibration

The default `PressureConfig` coefficients are placeholders. They produce
reasonable behavior on the synthetic scenarios shipped with IAIso, but
real workloads need empirical calibration.

IAIso ships infrastructure for doing this honestly:

- `iaiso.calibration.TrajectoryRecorder` — records agent executions
  without enforcing thresholds, so you can capture real pressure-relevant
  data from real runs.
- `iaiso.calibration.calibrate` — a grid search that fits coefficients
  separating benign from runaway trajectories.
- `python -m iaiso.calibration` — CLI.
- `scripts/run_calibration_study.py` — end-to-end calibration pipeline
  producing an auditable report.
- `scripts/record_swebench.py`, `record_gaia.py`, `record_generic.py` —
  ready-to-use instrumentation for specific benchmarks and custom agents.

## Workflow

### 1. Instrument your agent

Use `GenericTrajectoryLogger` (or the benchmark-specific equivalents) in
your agent's step loop:

```python
from scripts.record_generic import GenericTrajectoryLogger
import uuid

logger = GenericTrajectoryLogger(
    run_id=str(uuid.uuid4()),
    output_path="./trajectories/run-2026-04.jsonl",
    metadata={"agent_version": "v2.1", "workload": "customer-support"},
)

try:
    for step in agent.run(task):
        logger.observe_step(
            tokens=step.llm_tokens,
            tool_calls=step.tool_calls_made,
            depth=step.current_depth,
        )
    if agent_succeeded():
        logger.finalize(label="benign")
    else:
        logger.finalize(label="runaway" if hit_budget_limit else "ambiguous")
except AgentError:
    logger.finalize(label="runaway")
```

### 2. Collect data

Aim for at least 30 benign and 30 runaway trajectories; 100+ of each
class is better. Track metadata (agent version, model, workload type)
so you can slice the data later.

### 3. Run the calibration study

```bash
python scripts/run_calibration_study.py \
    --input ./trajectories/*.jsonl \
    --study-name production-agent-2026-04 \
    --seed 42
```

This writes to `./calibration_studies/production-agent-2026-04/`:

- `config.json` — recommended `PressureConfig`
- `report.md` — human-readable summary with all metrics and warnings
- `report.json` — machine-readable report for archival
- `calibration_set.jsonl` + `held_out_set.jsonl` — the exact data
  used, for reproducibility

### 4. Review the report

Before deploying the recommended config, check:

- **Sample size warnings.** The report emits a warning when n < 30 per
  class. Below that, the recommendation is unreliable.
- **Gap.** A positive gap means benign and runaway are separable by
  pressure; a negative gap means they aren't. If the gap is negative,
  no threshold will work well — you need additional guards, not just
  IAIso.
- **Held-out TPR/FPR.** These are the metrics you'll actually see in
  production. TPR = catch rate on runaways, FPR = false-alarm rate on
  benign runs.
- **Warnings.** Low F1, low gap, small sample size — all flagged.

### 5. Deploy and monitor

Even after calibration, monitor drift. Workloads change; your agent
might get more complex; the model might change. Emit pressure
trajectories from production (via the audit sink) and recalibrate
every few months, or whenever you see unexplained changes in
false-positive/false-negative rates.

## Labeling policy

The calibration harness requires each trajectory to be labeled
`"benign"`, `"runaway"`, or `"ambiguous"`. Ambiguous trajectories are
excluded from calibration.

- **benign**: The agent completed the task successfully. This is
  the positive example of "normal" behavior.
- **runaway**: The agent exhibited the pathological behavior IAIso
  exists to catch — ran until it hit a token or tool-call ceiling,
  entered a tool-call loop, or was manually terminated for
  runaway-like reasons.
- **ambiguous**: Outcome unclear. The agent might have failed for
  a reason unrelated to runaway behavior (task was too hard, data
  was missing, an unrelated error occurred). Including these as
  "runaway" will bias your calibration toward catching harder tasks
  rather than pathological agents.

If you can't confidently label a trajectory, mark it ambiguous.
Calibration on noisy labels is worse than calibration on fewer
clean labels.

## What this gives you vs. what it doesn't

Calibration produces a `PressureConfig` tuned to your workload. That's
real value. It does NOT produce:

- A safety guarantee. Calibration is empirical; it says "on this sample,
  these coefficients separated benign from runaway." Future runs may
  behave differently.
- Transferable coefficients. A config calibrated on customer-support
  agents will likely be wrong for code-generation agents.
- A substitute for other safeguards. Token budgets, tool-call
  quotas, per-tool policies, human review — IAIso is one layer in a
  defense-in-depth posture, not a replacement for the others.

## Running against public benchmarks

The `scripts/record_swebench.py` and `scripts/record_gaia.py` files
wrap IAIso trajectory recording around SWE-bench and GAIA agent runs.
Those benchmarks have their own harnesses (see
https://www.swebench.com/ and the GAIA Hugging Face dataset); this
repo does NOT re-implement them. You wire the logger into your agent,
run the benchmark, and feed the resulting JSONL into the calibration
pipeline.

Expected effort: setting up SWE-bench is typically a day or two; a
single full run on SWE-bench-Lite (300 instances) takes 4-12 hours and
costs $20-200 in API usage depending on the model. GAIA is lighter.
This is the "actual research" part that can't be shortcut — it's why
the previous version of IAIso's "calibration" was just made up
numbers, and why the right way to fix it is to ship the infrastructure
and have someone actually run the study.

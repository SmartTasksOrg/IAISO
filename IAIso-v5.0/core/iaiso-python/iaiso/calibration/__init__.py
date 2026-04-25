"""Empirical calibration harness.

Purpose: fit IAIso pressure coefficients to a real workload by measuring
pressure trajectories on known-benign and known-runaway runs.

This module provides the infrastructure; the user provides the runs. Running
this against synthetic data produces synthetic answers; running it against
real agent benchmarks (SWE-bench, GAIA, WebArena, or your own production
traces) produces real answers.

Workflow:

    1. Instrument your agent with a `TrajectoryRecorder` instead of (or in
       addition to) a PressureEngine.
    2. Run the agent on your benchmark. Label each completed run as
       "benign" (succeeded normally) or "runaway" (failed due to infinite
       loops, token exhaustion, tool spirals — the things IAIso should
       catch).
    3. Save trajectories to JSONL files.
    4. Feed the JSONL files into `calibrate()`, which searches
       coefficient space for settings that best separate benign from
       runaway trajectories.
    5. Validate the recommended coefficients on a held-out set of runs.

Honest limitations:

    - Coefficient fitting is a heuristic grid search over a reasonable
      parameter range. It is NOT a principled ML procedure with
      cross-validation guarantees.
    - "Best separation" is measured by a simple score (max(F1, AUROC) at
      chosen threshold); different scoring functions may give different
      recommendations.
    - The fit is only as good as the labels. Mislabeling "benign" runs
      that were actually runaways (or vice versa) will produce bad
      coefficients.
    - With <30 runs of each class, recommendations are unreliable. With
      <10, they are meaningless. The harness will warn but will not
      refuse.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from iaiso.core.engine import PressureConfig, PressureEngine, StepInput


# ---------------------------------------------------------------------------
# Recording trajectories
# ---------------------------------------------------------------------------


@dataclass
class TrajectoryStep:
    """One step of work in a recorded trajectory."""

    tokens: int = 0
    tool_calls: int = 0
    depth: int = 0
    elapsed_seconds: float = 0.0
    """Wall-clock seconds since the previous step (for D_time dissipation)."""


@dataclass
class Trajectory:
    """A full recorded run.

    Attributes:
        run_id: Unique identifier for this run.
        label: "benign" | "runaway" | "ambiguous". Required for calibration.
        steps: Ordered list of TrajectoryStep.
        metadata: Free-form (benchmark name, agent version, etc.).
    """

    run_id: str
    label: str
    steps: list[TrajectoryStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "run_id": self.run_id,
            "label": self.label,
            "metadata": self.metadata,
            "steps": [dataclasses.asdict(s) for s in self.steps],
        })

    @classmethod
    def from_json(cls, line: str) -> "Trajectory":
        obj = json.loads(line)
        return cls(
            run_id=obj["run_id"],
            label=obj["label"],
            metadata=obj.get("metadata", {}),
            steps=[TrajectoryStep(**s) for s in obj.get("steps", [])],
        )


class TrajectoryRecorder:
    """Drop-in replacement for PressureEngine during instrumentation.

    Records each step without enforcing thresholds. Call `finalize(label)`
    at the end of a run to produce a Trajectory object.
    """

    def __init__(self, run_id: str, metadata: dict[str, Any] | None = None) -> None:
        self._run_id = run_id
        self._metadata = metadata or {}
        self._steps: list[TrajectoryStep] = []

    def step(
        self,
        tokens: int = 0,
        tool_calls: int = 0,
        depth: int = 0,
        elapsed_seconds: float = 0.0,
    ) -> None:
        self._steps.append(TrajectoryStep(
            tokens=tokens,
            tool_calls=tool_calls,
            depth=depth,
            elapsed_seconds=elapsed_seconds,
        ))

    def finalize(self, label: str) -> Trajectory:
        if label not in ("benign", "runaway", "ambiguous"):
            raise ValueError(
                "label must be one of 'benign', 'runaway', 'ambiguous'"
            )
        return Trajectory(
            run_id=self._run_id,
            label=label,
            steps=list(self._steps),
            metadata=dict(self._metadata),
        )


def load_trajectories(path: str | Path) -> list[Trajectory]:
    """Load trajectories from a JSONL file."""
    result: list[Trajectory] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                result.append(Trajectory.from_json(line))
    return result


def save_trajectories(trajectories: Iterable[Trajectory], path: str | Path) -> None:
    """Save trajectories to a JSONL file."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for t in trajectories:
            f.write(t.to_json() + "\n")


# ---------------------------------------------------------------------------
# Replaying trajectories against configurations
# ---------------------------------------------------------------------------


def peak_pressure(trajectory: Trajectory, config: PressureConfig) -> float:
    """Replay a trajectory against a config and return the peak pressure reached.

    Uses a virtual clock derived from the trajectory's `elapsed_seconds`
    fields, so D_time dissipation is accounted for without requiring the
    original wall-clock timing.
    """
    virtual_time = [0.0]

    def clock() -> float:
        return virtual_time[0]

    # Set thresholds to 1.0 so the engine never locks during replay.
    replay_cfg = dataclasses.replace(
        config,
        escalation_threshold=0.999,
        release_threshold=1.0,
    )
    engine = PressureEngine(
        replay_cfg,
        execution_id=f"replay-{trajectory.run_id}",
        clock=clock,
    )

    peak = 0.0
    for s in trajectory.steps:
        virtual_time[0] += s.elapsed_seconds
        engine.step(StepInput(
            tokens=s.tokens,
            tool_calls=s.tool_calls,
            depth=s.depth,
        ))
        peak = max(peak, engine.pressure)
    return peak


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


@dataclass
class CalibrationResult:
    """Output of a calibration run.

    Attributes:
        config: Recommended PressureConfig.
        escalation_threshold: Recommended escalation threshold, chosen to
            maximize separation between benign and runaway peak pressures.
        release_threshold: Recommended release threshold.
        f1_at_threshold: F1 score at the escalation threshold on the
            training set.
        benign_peak_p95: 95th percentile of benign peak pressure.
        benign_peak_p99: 99th percentile of benign peak pressure.
        runaway_peak_p05: 5th percentile of runaway peak pressure.
        runaway_peak_p50: Median runaway peak pressure.
        gap: runaway_peak_p05 - benign_peak_p95. Positive = separable.
        n_benign: Number of benign trajectories used.
        n_runaway: Number of runaway trajectories used.
        warnings: Non-empty list of warnings about the calibration.
    """

    config: PressureConfig
    escalation_threshold: float
    release_threshold: float
    f1_at_threshold: float
    benign_peak_p95: float
    benign_peak_p99: float
    runaway_peak_p05: float
    runaway_peak_p50: float
    gap: float
    n_benign: int
    n_runaway: int
    warnings: list[str] = field(default_factory=list)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[f] * (c - k) + values[c] * (k - f)


def _f1_at_threshold(
    benign_peaks: list[float],
    runaway_peaks: list[float],
    threshold: float,
) -> float:
    tp = sum(1 for p in runaway_peaks if p >= threshold)
    fn = sum(1 for p in runaway_peaks if p < threshold)
    fp = sum(1 for p in benign_peaks if p >= threshold)
    if tp == 0:
        return 0.0
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


DEFAULT_COEFFICIENT_GRID = {
    "token_coefficient": [0.005, 0.010, 0.015, 0.020, 0.030, 0.050],
    "tool_coefficient": [0.02, 0.05, 0.08, 0.12, 0.20],
    "depth_coefficient": [0.02, 0.05, 0.10, 0.20],
    "dissipation_per_step": [0.0, 0.01, 0.02, 0.05, 0.10],
    "dissipation_per_second": [0.0],  # only search this if trajectories have real timing
}


def calibrate(
    trajectories: list[Trajectory],
    coefficient_grid: dict[str, list[float]] | None = None,
    target_benign_percentile: float = 0.95,
    target_runaway_percentile: float = 0.05,
    verbose: bool = False,
) -> CalibrationResult:
    """Find PressureConfig coefficients that separate benign from runaway runs.

    Strategy:
        1. Grid search over coefficient combinations.
        2. For each combination, replay all trajectories, compute peak
           pressures.
        3. Score the combination by the gap:
               runaway_peak_p05 - benign_peak_p95
           A positive gap means a threshold in that range correctly
           classifies most of both classes.
        4. Among combinations with positive gap, pick the one with
           highest F1 at a threshold placed at the midpoint of the gap.
        5. If no combination has a positive gap, pick the one with the
           largest negative gap (least-bad separation) and emit a
           warning.

    Returns a `CalibrationResult` with the recommended config and
    diagnostic statistics. Always inspect warnings and the statistics
    before deploying the config.
    """
    benign = [t for t in trajectories if t.label == "benign"]
    runaway = [t for t in trajectories if t.label == "runaway"]

    warnings_list: list[str] = []
    if len(benign) < 10 or len(runaway) < 10:
        warnings_list.append(
            f"Low sample count: {len(benign)} benign, {len(runaway)} runaway. "
            "Results are unreliable below 10 runs per class, meaningless below 30."
        )
    if len(benign) < 30 or len(runaway) < 30:
        warnings_list.append(
            f"Moderate sample count: {len(benign)} benign, {len(runaway)} runaway. "
            "Consider collecting more before deploying the recommended config."
        )

    grid = coefficient_grid or DEFAULT_COEFFICIENT_GRID
    grid_keys = list(grid.keys())
    grid_values = [grid[k] for k in grid_keys]

    best: CalibrationResult | None = None

    for combo in itertools.product(*grid_values):
        coeffs = dict(zip(grid_keys, combo))
        try:
            candidate_cfg = PressureConfig(
                escalation_threshold=0.85,
                release_threshold=0.95,
                **coeffs,
            )
        except ValueError:
            continue

        benign_peaks = [peak_pressure(t, candidate_cfg) for t in benign]
        runaway_peaks = [peak_pressure(t, candidate_cfg) for t in runaway]

        bp95 = _percentile(benign_peaks, target_benign_percentile)
        bp99 = _percentile(benign_peaks, 0.99)
        rp05 = _percentile(runaway_peaks, target_runaway_percentile)
        rp50 = _percentile(runaway_peaks, 0.5)
        gap = rp05 - bp95

        # Place threshold at midpoint of gap if positive, else at benign p95
        threshold = (bp95 + rp05) / 2 if gap > 0 else bp95
        # Clamp to [0, 1)
        threshold = max(0.001, min(0.999, threshold))
        f1 = _f1_at_threshold(benign_peaks, runaway_peaks, threshold)

        # Choose release_threshold halfway between escalation and 1.0
        release = min(0.99, threshold + (1.0 - threshold) / 2)
        try:
            final_cfg = PressureConfig(
                escalation_threshold=threshold,
                release_threshold=release,
                **coeffs,
            )
        except ValueError:
            continue

        if verbose:
            print(f"coeffs={coeffs} gap={gap:+.3f} f1={f1:.3f} "
                  f"thresh={threshold:.3f}")

        candidate = CalibrationResult(
            config=final_cfg,
            escalation_threshold=threshold,
            release_threshold=release,
            f1_at_threshold=f1,
            benign_peak_p95=bp95,
            benign_peak_p99=bp99,
            runaway_peak_p05=rp05,
            runaway_peak_p50=rp50,
            gap=gap,
            n_benign=len(benign),
            n_runaway=len(runaway),
            warnings=[],
        )

        if best is None:
            best = candidate
        elif (candidate.gap > 0 and best.gap <= 0):
            best = candidate  # prefer positive gap
        elif (candidate.gap > 0 and best.gap > 0
              and candidate.f1_at_threshold > best.f1_at_threshold):
            best = candidate  # better F1 in separable regime
        elif (candidate.gap <= 0 and best.gap <= 0
              and candidate.gap > best.gap):
            best = candidate  # less-bad gap in non-separable regime

    if best is None:
        raise RuntimeError("No valid coefficient combinations in grid")

    if best.gap <= 1e-6:
        warnings_list.append(
            f"No coefficient combination separates benign from runaway "
            f"cleanly (best gap: {best.gap:+.3f}). Pressure alone may not "
            f"be a sufficient signal for your workload; consider combining "
            f"with other guards."
        )
    if best.f1_at_threshold < 0.7:
        warnings_list.append(
            f"Best F1 score is low ({best.f1_at_threshold:.3f}). The "
            f"recommended config will have substantial false-positive or "
            f"false-negative rates."
        )

    return dataclasses.replace(best, warnings=warnings_list)


def validate(
    trajectories: list[Trajectory],
    config: PressureConfig,
) -> dict[str, float]:
    """Evaluate a PressureConfig on a held-out set of trajectories.

    Returns a dict with: tpr (true positive rate on runaway),
    fpr (false positive rate on benign), f1.
    """
    benign = [t for t in trajectories if t.label == "benign"]
    runaway = [t for t in trajectories if t.label == "runaway"]
    if not benign or not runaway:
        raise ValueError("Validation requires both benign and runaway trajectories")

    benign_peaks = [peak_pressure(t, config) for t in benign]
    runaway_peaks = [peak_pressure(t, config) for t in runaway]
    thr = config.escalation_threshold

    tp = sum(1 for p in runaway_peaks if p >= thr)
    fn = sum(1 for p in runaway_peaks if p < thr)
    fp = sum(1 for p in benign_peaks if p >= thr)
    tn = sum(1 for p in benign_peaks if p < thr)

    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tpr
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)

    return {
        "tpr": tpr,
        "fpr": fpr,
        "f1": f1,
        "n_benign": len(benign),
        "n_runaway": len(runaway),
        "benign_peak_mean": statistics.mean(benign_peaks),
        "benign_peak_stdev": (statistics.stdev(benign_peaks)
                              if len(benign_peaks) > 1 else 0.0),
        "runaway_peak_mean": statistics.mean(runaway_peaks),
        "runaway_peak_stdev": (statistics.stdev(runaway_peaks)
                                if len(runaway_peaks) > 1 else 0.0),
    }

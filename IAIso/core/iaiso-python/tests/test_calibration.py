"""Tests for the empirical calibration harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from iaiso import PressureConfig
from iaiso.calibration import (
    Trajectory,
    TrajectoryRecorder,
    TrajectoryStep,
    calibrate,
    load_trajectories,
    peak_pressure,
    save_trajectories,
    validate,
)


def test_recorder_builds_trajectory() -> None:
    rec = TrajectoryRecorder("run-1", metadata={"agent": "test"})
    rec.step(tokens=100, tool_calls=1)
    rec.step(tokens=200, depth=1, elapsed_seconds=1.5)
    traj = rec.finalize("benign")
    assert traj.run_id == "run-1"
    assert traj.label == "benign"
    assert len(traj.steps) == 2
    assert traj.steps[1].elapsed_seconds == pytest.approx(1.5)
    assert traj.metadata == {"agent": "test"}


def test_recorder_rejects_bad_label() -> None:
    rec = TrajectoryRecorder("r")
    with pytest.raises(ValueError):
        rec.finalize("success")


def test_trajectory_json_roundtrip(tmp_path: Path) -> None:
    trajectories = [
        Trajectory(
            run_id=f"r{i}",
            label="benign" if i % 2 == 0 else "runaway",
            steps=[TrajectoryStep(tokens=100 + i, tool_calls=i)],
            metadata={"i": i},
        )
        for i in range(3)
    ]
    path = tmp_path / "trajectories.jsonl"
    save_trajectories(trajectories, path)
    loaded = load_trajectories(path)
    assert len(loaded) == 3
    assert loaded[0].run_id == "r0"
    assert loaded[1].label == "runaway"
    assert loaded[2].metadata == {"i": 2}


def test_peak_pressure_replay() -> None:
    traj = Trajectory(
        run_id="r",
        label="benign",
        steps=[
            TrajectoryStep(tokens=1000),
            TrajectoryStep(tokens=1000),
        ],
    )
    # With token_coefficient=0.1 and step dissipation=0.02:
    # Step 1: +0.1, -0.02 = 0.08
    # Step 2: +0.1, -0.02 = 0.16
    cfg = PressureConfig(
        token_coefficient=0.1,
        tool_coefficient=0.0,
        depth_coefficient=0.0,
        dissipation_per_step=0.02,
    )
    peak = peak_pressure(traj, cfg)
    assert peak == pytest.approx(0.16)


def test_calibrate_finds_separating_coefficients() -> None:
    # Benign: short, moderate work
    benign_trajectories = [
        Trajectory(
            run_id=f"b{i}",
            label="benign",
            steps=[TrajectoryStep(tokens=200, tool_calls=1) for _ in range(5)],
        )
        for i in range(30)
    ]
    # Runaway: long tool-call loops
    runaway_trajectories = [
        Trajectory(
            run_id=f"r{i}",
            label="runaway",
            steps=[TrajectoryStep(tokens=100, tool_calls=5) for _ in range(25)],
        )
        for i in range(30)
    ]
    result = calibrate(benign_trajectories + runaway_trajectories)

    # There SHOULD be a separating coefficient combination for this clean synthetic
    # benign/runaway split. If this test starts failing, either the grid got too
    # coarse or the calibration logic broke.
    assert result.gap > 0, (
        f"Expected positive gap on synthetic clean data, got {result.gap:+.3f}"
    )
    assert result.f1_at_threshold > 0.8
    assert result.n_benign == 30
    assert result.n_runaway == 30


def test_calibrate_warns_on_small_sample() -> None:
    trajectories = [
        Trajectory(
            run_id=f"b{i}",
            label="benign",
            steps=[TrajectoryStep(tokens=200)],
        )
        for i in range(3)
    ] + [
        Trajectory(
            run_id=f"r{i}",
            label="runaway",
            steps=[TrajectoryStep(tokens=100, tool_calls=5) for _ in range(20)],
        )
        for i in range(3)
    ]
    result = calibrate(trajectories)
    assert any("unreliable" in w.lower() for w in result.warnings)


def test_calibrate_warns_on_unseparable_classes() -> None:
    # Identical behavior for both classes — no coefficient can separate them.
    trajectories = [
        Trajectory(
            run_id=f"b{i}",
            label="benign",
            steps=[TrajectoryStep(tokens=500, tool_calls=1)],
        )
        for i in range(30)
    ] + [
        Trajectory(
            run_id=f"r{i}",
            label="runaway",
            steps=[TrajectoryStep(tokens=500, tool_calls=1)],
        )
        for i in range(30)
    ]
    result = calibrate(trajectories)
    # Gap should be zero or near-zero
    assert result.gap <= 0.01
    assert any("separate" in w.lower() or "signal" in w.lower()
               for w in result.warnings)


def test_validate_reports_held_out_metrics() -> None:
    benign = [
        Trajectory(
            run_id=f"b{i}",
            label="benign",
            steps=[TrajectoryStep(tokens=100) for _ in range(3)],
        )
        for i in range(10)
    ]
    runaway = [
        Trajectory(
            run_id=f"r{i}",
            label="runaway",
            steps=[TrajectoryStep(tokens=100, tool_calls=3) for _ in range(15)],
        )
        for i in range(10)
    ]
    cfg = PressureConfig(
        token_coefficient=0.01,
        tool_coefficient=0.08,
        dissipation_per_step=0.01,
        escalation_threshold=0.5,
        release_threshold=0.9,
    )
    metrics = validate(benign + runaway, cfg)
    assert 0.0 <= metrics["tpr"] <= 1.0
    assert 0.0 <= metrics["fpr"] <= 1.0
    assert metrics["n_benign"] == 10
    assert metrics["n_runaway"] == 10

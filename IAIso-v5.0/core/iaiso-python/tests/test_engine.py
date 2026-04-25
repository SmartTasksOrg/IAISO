"""Tests for the core pressure engine."""

from __future__ import annotations

import pytest

from iaiso import (
    Lifecycle,
    MemorySink,
    PressureConfig,
    PressureEngine,
    StepInput,
    StepOutcome,
)


def test_fresh_engine_starts_at_zero() -> None:
    engine = PressureEngine(PressureConfig(), execution_id="t1")
    snap = engine.snapshot()
    assert snap.pressure == 0.0
    assert snap.step == 0
    assert snap.lifecycle is Lifecycle.INIT


def test_step_accumulates_pressure() -> None:
    cfg = PressureConfig(
        token_coefficient=0.01,
        tool_coefficient=0.05,
        dissipation_per_step=0.0,
    )
    engine = PressureEngine(cfg, execution_id="t1")
    outcome = engine.step(StepInput(tokens=1000, tool_calls=1))
    # 1000/1000 * 0.01 + 1 * 0.05 = 0.06
    assert engine.pressure == pytest.approx(0.06)
    assert outcome is StepOutcome.OK
    assert engine.lifecycle is Lifecycle.RUNNING


def test_dissipation_reduces_pressure() -> None:
    cfg = PressureConfig(
        token_coefficient=0.1,
        tool_coefficient=0.0,
        dissipation_per_step=0.05,
    )
    engine = PressureEngine(cfg, execution_id="t1")
    engine.step(StepInput(tokens=1000))  # +0.1, -0.05 = 0.05
    assert engine.pressure == pytest.approx(0.05)
    engine.step(StepInput(tokens=0))  # +0, -0.05 = 0.0
    assert engine.pressure == pytest.approx(0.0)


def test_escalation_fires_at_threshold() -> None:
    cfg = PressureConfig(
        escalation_threshold=0.5,
        release_threshold=0.9,
        token_coefficient=0.6,
        dissipation_per_step=0.0,
    )
    engine = PressureEngine(cfg, execution_id="t1")
    outcome = engine.step(StepInput(tokens=1000))
    assert outcome is StepOutcome.ESCALATED
    assert engine.lifecycle is Lifecycle.ESCALATED


def test_release_fires_and_locks() -> None:
    cfg = PressureConfig(
        escalation_threshold=0.5,
        release_threshold=0.8,
        token_coefficient=1.0,
        dissipation_per_step=0.0,
        post_release_lock=True,
    )
    engine = PressureEngine(cfg, execution_id="t1")
    outcome = engine.step(StepInput(tokens=1000))
    assert outcome is StepOutcome.RELEASED
    assert engine.lifecycle is Lifecycle.LOCKED
    assert engine.pressure == 0.0


def test_locked_engine_rejects_further_steps() -> None:
    cfg = PressureConfig(
        escalation_threshold=0.5,
        release_threshold=0.8,
        token_coefficient=1.0,
        post_release_lock=True,
    )
    engine = PressureEngine(cfg, execution_id="t1")
    engine.step(StepInput(tokens=1000))  # releases + locks
    outcome = engine.step(StepInput(tokens=100))
    assert outcome is StepOutcome.LOCKED


def test_reset_clears_lock() -> None:
    cfg = PressureConfig(
        escalation_threshold=0.5,
        release_threshold=0.8,
        token_coefficient=1.0,
        post_release_lock=True,
    )
    engine = PressureEngine(cfg, execution_id="t1")
    engine.step(StepInput(tokens=1000))
    engine.reset()
    assert engine.lifecycle is Lifecycle.INIT
    outcome = engine.step(StepInput(tokens=100))
    assert outcome is StepOutcome.OK


def test_audit_events_emitted() -> None:
    sink = MemorySink()
    engine = PressureEngine(PressureConfig(), execution_id="t1", audit_sink=sink)
    engine.step(StepInput(tokens=100))

    kinds = [e.kind for e in sink.events]
    assert "engine.init" in kinds
    assert "engine.step" in kinds


def test_invalid_config_rejected() -> None:
    with pytest.raises(ValueError):
        PressureConfig(escalation_threshold=-0.1)
    with pytest.raises(ValueError):
        PressureConfig(escalation_threshold=0.9, release_threshold=0.5)
    with pytest.raises(ValueError):
        PressureConfig(token_coefficient=-1.0)


def test_no_lock_allows_continued_operation() -> None:
    cfg = PressureConfig(
        escalation_threshold=0.5,
        release_threshold=0.8,
        token_coefficient=1.0,
        post_release_lock=False,
    )
    engine = PressureEngine(cfg, execution_id="t1")
    engine.step(StepInput(tokens=1000))  # releases, resets, does NOT lock
    assert engine.lifecycle is Lifecycle.RUNNING
    assert engine.pressure == 0.0
    outcome = engine.step(StepInput(tokens=100))
    assert outcome is StepOutcome.OK

"""Tests for the cross-execution pressure coordinator."""

from __future__ import annotations

import threading

import pytest

from iaiso import MemorySink
from iaiso.coordination import (
    CoordinatorConfig,
    MaxAggregator,
    MeanAggregator,
    SharedPressureCoordinator,
    SumAggregator,
    WeightedSumAggregator,
)


def test_sum_aggregator_grows_with_fleet() -> None:
    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=1.5, release_threshold=2.5),
        aggregator=SumAggregator(),
    )
    coord.register("a")
    coord.register("b")
    coord.update("a", 0.6)
    snap = coord.update("b", 0.6)
    assert snap.aggregate_pressure == pytest.approx(1.2)
    assert snap.lifecycle == "nominal"


def test_mean_aggregator_stays_bounded() -> None:
    coord = SharedPressureCoordinator(aggregator=MeanAggregator())
    coord.register("a")
    coord.register("b")
    coord.register("c")
    coord.update("a", 0.9)
    coord.update("b", 0.9)
    snap = coord.update("c", 0.9)
    assert snap.aggregate_pressure == pytest.approx(0.9)
    assert snap.aggregate_pressure <= 1.0


def test_max_detects_single_agent_runaway() -> None:
    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=0.8, release_threshold=0.95),
        aggregator=MaxAggregator(),
    )
    coord.register("sleepy")
    coord.register("runaway")
    coord.update("sleepy", 0.1)
    snap = coord.update("runaway", 0.9)
    assert snap.aggregate_pressure == pytest.approx(0.9)
    assert snap.lifecycle == "escalated"


def test_weighted_sum_aggregator() -> None:
    agg = WeightedSumAggregator(
        weights={"expensive": 3.0, "cheap": 0.5},
        default_weight=1.0,
    )
    coord = SharedPressureCoordinator(aggregator=agg)
    coord.update("expensive", 0.5)  # contributes 1.5
    coord.update("cheap", 0.8)      # contributes 0.4
    coord.update("default", 0.2)    # contributes 0.2
    snap = coord.snapshot()
    assert snap.aggregate_pressure == pytest.approx(2.1)


def test_escalation_callback_fires() -> None:
    calls: list[float] = []
    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=1.0, release_threshold=2.0),
        aggregator=SumAggregator(),
        on_escalation=lambda snap: calls.append(snap.aggregate_pressure),
    )
    coord.update("a", 0.5)
    coord.update("b", 0.6)  # aggregate crosses 1.0
    assert len(calls) == 1
    assert calls[0] == pytest.approx(1.1)


def test_release_callback_fires_once() -> None:
    calls: list[float] = []
    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=1.0, release_threshold=2.0),
        aggregator=SumAggregator(),
        on_release=lambda snap: calls.append(snap.aggregate_pressure),
    )
    coord.update("a", 1.0)
    coord.update("b", 1.0)
    coord.update("c", 0.5)  # already released, should not re-fire
    assert len(calls) == 1


def test_return_to_nominal_after_unregister() -> None:
    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=1.0, release_threshold=2.0),
        aggregator=SumAggregator(),
    )
    coord.update("a", 0.8)
    coord.update("b", 0.8)
    assert coord.snapshot().lifecycle == "escalated"
    coord.unregister("a")
    coord.unregister("b")
    assert coord.snapshot().lifecycle == "nominal"


def test_audit_events_emitted() -> None:
    sink = MemorySink()
    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=1.0, release_threshold=2.0),
        audit_sink=sink,
    )
    coord.register("a")
    coord.update("a", 0.5)
    coord.update("a", 1.0)  # triggers escalation at sum=1.0
    kinds = [e.kind for e in sink.events]
    assert "coordinator.init" in kinds
    assert "coordinator.execution_registered" in kinds
    assert "coordinator.escalation" in kinds


def test_concurrent_updates_are_thread_safe() -> None:
    coord = SharedPressureCoordinator(
        config=CoordinatorConfig(escalation_threshold=100.0, release_threshold=200.0),
    )
    n_threads = 20
    updates_per_thread = 100

    def worker(idx: int) -> None:
        eid = f"exec-{idx}"
        coord.register(eid)
        for i in range(updates_per_thread):
            coord.update(eid, (i % 10) / 10.0)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snap = coord.snapshot()
    assert snap.active_executions == n_threads


def test_invalid_pressure_rejected() -> None:
    coord = SharedPressureCoordinator()
    with pytest.raises(ValueError):
        coord.update("a", -0.1)
    with pytest.raises(ValueError):
        coord.update("a", 1.5)


def test_invalid_config_rejected() -> None:
    with pytest.raises(ValueError):
        CoordinatorConfig(escalation_threshold=-1.0)
    with pytest.raises(ValueError):
        CoordinatorConfig(escalation_threshold=2.0, release_threshold=1.0)
